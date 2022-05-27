import queue
import threading
import sys
import time

from lib.mux_demux.mux_demux_stream import MuxDemuxStream
from lib.utils import MTByteStream

from .packet import *

from loguru import logger

CONNACK_WAIT_TIMEOUT = 0.1
ACK_WAIT_TIMEOUT = 0.1

# No envie el CONNECT (si soy socket) ni lo recibi (si soy listener)
NOT_CONNECTED = "NOT_CONNECTED"
# Soy Socket de listener, mande el CONNACK y ya recibi info
# (confirma que el cliente recibio el CONNECT)
CONNECTING = "CONNECTING"
# Soy Socket de listener, y recibi el CONNECT
CONNECTED = "CONNECTED"
# Mande FIN, pero no recibi FINACK
DISCONNECTING = "DISCONNECTING"
# Mande FIN y recibi FINACK
DISCONNECTED = "DISCONNECTED"

# implement thread safe variable status
class MTStatus:
    def __init__(self):
        self.status = NOT_CONNECTED
        self.lock = threading.Lock()

    def set(self, status):
        with self.lock:
            self.status = status

    def is_equal(self, status):
        with self.lock:
            return self.status == status

    def __repr__(self):
        return self.status


class SAWSocket:
    def __init__(self):
        self.socket = None
        self.packet_thread_handler = None
        self.expected_packet_number = 0
        self.next_packet_number_to_send = 0

        self.timeout = None
        self.block = True

        self.is_from_listener = None
        self.status = MTStatus()

        self.ack_queue = queue.Queue()
        self.info_bytestream = None
        # Only for connect
        self.stop_event = threading.Event()

        # Only for listener
        self.connect_event = threading.Event()

    def from_listener(self, mux_demux_socket):
        self.is_from_listener = True
        self.socket = mux_demux_socket

        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.packet_thread_handler.start()
        self.info_bytestream = MTByteStream()
        # Wait for CONNECT
        self.connect_event.wait()

    def connect(self, addr):
        self.is_from_listener = False
        logger.info(f"Connecting to {addr[0]}:{addr[1]}")
        self.socket = MuxDemuxStream()
        self.socket.connect(addr)
        self.socket.settimeout(CONNACK_WAIT_TIMEOUT)
        self.socket.setblocking(True)
        while True:
            try:
                logger.debug("Sending connect packet")
                self.socket.send_all(bytes(ConnectPacket()))
                logger.debug("Waiting for connack packet")

                PacketFactory.read_connack(self.socket)
                self.socket.send_all(bytes(InfoPacket(number=self.next_packet_number_to_send, body=b"")))
                self.next_packet_number_to_send += 1
                self.status.set(CONNECTED)
                logger.debug("Setting event")
                self.connect_event.set()
                self.socket.settimeout(None)
                break
            except socket.timeout:
                logger.debug("Time out waiting for CONNACK, sending again")
            except ProtocolViolation:
                logger.error("Protocol violation, closing connection")
                self.socket.close()
                self.status.set(DISCONNECTED)
                return

        logger.debug("Connected")
        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.packet_thread_handler.start()
        self.info_bytestream = MTByteStream()

    def packet_handler(self):
        logger.debug("Packet handler started")
        self.socket.settimeout(1)
        self.socket.setblocking(True)
        while True:
            try:
                packet = PacketFactory.read_from_stream(self.socket)
                packet.be_handled_by(self)
            except socket.timeout:
                # check if stop event is set
                if self.stop_event.is_set():
                    logger.debug("Exiting packet handler thread")
                    return

            except ProtocolViolation:
                logger.error("Protocol violation, closing connection")
                self.socket.close()
                self.status.set(DISCONNECTED)
                return

    def handle_info(self, packet):
        if self.status.is_equal(NOT_CONNECTED):
            # logger.error("Received INFO packet while not connected")
            raise Exception("Received INFO packet while not connected")
        elif self.status.is_equal(CONNECTING):
            # Confirmo que ya se recibio el CONNACK
            logger.debug("Received INFO packet while connecting, now fully connected")
            self.status.set(CONNECTED)

        if self.expected_packet_number == packet.number:
            logger.debug(
                f"Received expected INFO packet (Nº {packet.number}) (data: {packet.body})"
            )
            self.socket.send_all(bytes(AckPacket()))
            self.info_bytestream.put_bytes(packet.body)
            self.expected_packet_number += 1
        # TODO: hay que chequear que sea MENOR, porque puede pasar que el paquete
        # se demore en la red
        # Tambien hay que reiniciar el contador cada cierto tiempo
        elif (
            packet.number == self.expected_packet_number - 1
        ):
            logger.debug(f"Received INFO retransmission. Expecting {self.expected_packet_number}, received {packet.number}")
            self.socket.send_all(bytes(AckPacket()))
        else:
            logger.error(
                "Received unexpected INFO packet, dropping (expected %s,"
                " received %s)"
                % (
                    self.expected_packet_number,
                    packet.headers["packet_number"],
                )
            )
            raise Exception(
                "Received unexpected INFO packet, dropping (expected %s,"
                " received %s)"
                % (
                    self.expected_packet_number,
                    packet.headers["packet_number"],
                )
            )

    def handle_connect(self, packet):
        logger.debug("Received CONNECT packet")

        if self.is_from_listener:
            if self.status.is_equal(NOT_CONNECTED) or self.status.is_equal(CONNECTING):
                self.status.set(CONNECTING)
                self.connect_event.set()
                logger.debug("Sending CONNACK")
                self.socket.send_all(bytes(ConnackPacket()))
            else:  # self.status == CONNECTED
                logger.error("Received connect packet while already connected")
        else:  # socket from client
            logger.error("Received connect packet from server")

    def handle_connack(self, packet):
        logger.debug("Received CONNACK packet")

        if self.is_from_listener:
            logger.error("Received connack packet being socket from listener")
        else:
            if self.status.is_equal(CONNECTING):
                self.status.set(CONNECTED)
                logger.debug("Connected")
            else:
                logger.error(
                    "Received connack packet while not connecting (status: %s)"
                    % self.status
                )

    def handle_ack(self, packet):
        logger.debug("Received ACK packet")

        if not self.status.is_equal(CONNECTED):
            logger.error(f"Receiving ACK packet while not connected (status: {self.status})")
        else:
            logger.debug("Receiving ACK packet")
            self.ack_queue.put(packet)

    def handle_fin(self, packet):
        logger.debug("Received FIN packet")

        if self.status.is_equal(DISCONNECTED):
            logger.error(f"Receiving FIN packet but it was already disconnected")
        else:
            logger.debug("Receiving FIN packet")
            self.socket.send_all(bytes(FinackPacket()))
            self.status.set(DISCONNECTING)

    def handle_finack(self, packet):
        logger.debug("Received FINACK packet")

        if not self.status.is_equal(DISCONNECTING):
            logger.error("Receiving FINACK packet while not disconnecting")
        else:
            logger.debug("Receiving FINACK packet")
            self.ack_queue.put(packet)

    def send(self, buffer):
        logger.debug(f"Sending buffer {buffer}")

        if not self.status.is_equal(CONNECTED):
            logger.error("Trying to send data while not connected")
        else:
            logger.debug("Sending data")
            packets = InfoPacket.split(4, buffer, initial_number=self.next_packet_number_to_send)
            logger.debug("Fragmented buffer into %d packets" % len(packets))
            self.next_packet_number_to_send += len(packets)

            for packet in packets:
                logger.debug(
                    f"Sending packet Nº {packet.number}, data: {packet.body}"
                )
                while True:
                    self.socket.send_all(bytes(packet))
                    try:
                        ack = self.ack_queue.get(timeout=ACK_WAIT_TIMEOUT)
                        logger.debug("Received ACK packet")
                        break
                    except queue.Empty:
                        logger.error(
                            "Timeout waiting for ACK packet, sending again"
                        )

    def recv(self, buff_size):
        if self.status.is_equal(NOT_CONNECTED):
            logger.error("Trying to receive data while not connected")
            raise Exception(
                "Trying to receive data while not connected (status"
                f" {self.status})"
            )
        else:
            #logger.debug(f"Receiving data (buff_size {buff_size}), timeout {self.socket.gettimeout()}, blocking {self.socket.getblocking()}")
            try:
                info_body_bytes = self.info_bytestream.get_bytes(
                    buff_size, timeout=self.timeout, block=self.block
                )
                if len(info_body_bytes) > 0:
                    logger.debug(
                        "Received INFO packet (%d bytes)" % len(info_body_bytes)
                    )
                    return info_body_bytes
                else:
                    return b""
            except socket.timeout:
                logger.debug("Received no INFO packet")
                return b""

    def close(self):
        if self.status.is_equal(CONNECTED):
            logger.debug("Disconnecting")
            self.status.set(DISCONNECTING)
            self.socket.send_all(bytes(FinPacket()))
            logger.debug("Waiting for FINACK packet")
            while True:
                try:
                    finack = self.ack_queue.get(timeout=10)
                    logger.debug("Received FINACK packet")
                    break
                except queue.Empty:
                    logger.error("Timeout waiting for FINACK packet, sending again")
            self.status.set(DISCONNECTING)
            self.stop_event.set()
            self.socket.close()
        else:
            logger.debug(f"Closing socket (Status: {self.status})")
            self.stop_event.set()
            self.socket.close()

    def settimeout(self, timeout):
        self.timeout = timeout

    def setblocking(self, block):
        self.block = block
