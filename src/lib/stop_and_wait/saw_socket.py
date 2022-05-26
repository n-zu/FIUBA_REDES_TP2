import logging
import math
import queue
import socket
import threading
from lib.mux_demux.stream import MuxDemuxStream
from lib.utils import MTByteStream
from lib.stop_and_wait.packet import Packet

from .packet import *

logger = logging.getLogger(__name__)

CONNACK_WAIT_TIMEOUT = 500

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


class SAWSocket:
    def __init__(self):
        self.socket = None
        self.packet_thread_handler = None
        self.expected_packet_number = 0

        self.is_from_listener = None
        self.status = NOT_CONNECTED

        self.ack_queue = queue.Queue()
        self.info_bytestream = None

    def from_listener(self, mux_demux_socket):
        self.is_from_listener = True
        self.socket = mux_demux_socket

        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.packet_thread_handler.start()
        self.info_bytestream = MTByteStream()

    def connect(self, addr):
        self.is_from_listener = False
        logger.debug(f"Connecting to {addr[0]}:{addr[1]}")
        self.socket = MuxDemuxStream()
        self.socket.connect(addr)
        # self.socket.setblocking(False)
        self.socket.settimeout(CONNACK_WAIT_TIMEOUT)
        while True:
            try:
                logger.debug("Sending connect packet")
                self.socket.send_all(Packet.connect().encode())
                logger.debug("Waiting for connack packet")
                packet = Packet.read_from_stream(self.socket)
                if packet.type == CONNACK:
                    self.status = CONNECTED
                    break
                else:
                    logger.error(
                        "Received unexpected packet type (expected CONNACK)"
                    )
            except socket.timeout:
                logger.debug("Time out waiting for CONNACK, sending again")
        logger.debug("Connected")
        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.packet_thread_handler.start()
        self.info_bytestream = MTByteStream()

    def packet_handler(self):
        logger.debug("Packet handler started")
        while True:
            packet = Packet.read_from_stream(self.socket)
            logger.debug(
                f"Received packet {packet.type} with headers"
                f" {packet.headers} and body {packet.body}"
            )
            if packet.type == CONNECT:
                self.handle_connect(packet)
            elif packet.type == CONNACK:
                self.handle_connack(packet)
            elif packet.type == INFO:
                self.handle_info(packet)
            elif packet.type == ACK:
                self.handle_ack(packet)
            elif packet.type == FIN:
                self.handle_fin(packet)
            elif packet.type == FINACK:
                self.handle_finack(packet)
            else:
                logger.error("Received unknown packet type")
                raise Exception("Received unknown packet type")

    def handle_info(self, packet):
        if self.status == NOT_CONNECTED:
            # logger.error("Received INFO packet while not connected")
            raise Exception("Received INFO packet while not connected")
        elif self.status == CONNECTING:
            # Confirmo que ya se recibio el CONNACK
            self.status = CONNECTED

        if self.expected_packet_number == packet.headers["packet_number"]:
            logger.debug(
                "Received expected INFO packet (number %d)"
                % packet.headers["packet_number"]
            )
            self.socket.send_all(Packet.ack().encode())
            self.info_bytestream.put_bytes(packet.body)
            self.expected_packet_number += 1
        elif (
            packet.headers["packet_number"] == self.expected_packet_number - 1
        ):
            logger.debug("Received INFO retransmission")
            self.socket.send_all(Packet.ack().encode())
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
        if self.is_from_listener:
            if self.status == NOT_CONNECTED or self.status == CONNECTING:
                self.status = CONNECTING
                self.socket.send_all(Packet.connack().encode())
            else:  # self.status == CONNECTED
                logger.error("Received connect packet while already connected")
        else:  # socket from client
            logger.error("Received connect packet from server")

    def handle_connack(self, packet):
        if self.is_from_listener:
            logger.error("Received connack packet being socket from listener")
        else:
            if self.status == CONNECTING:
                self.status = CONNECTED
                logger.debug("Connected")
            else:
                logger.error(
                    "Received connack packet while not connecting (status: %s)"
                    % self.status
                )

    def handle_ack(self, packet):
        if self.status != CONNECTED:
            logger.error("Receiving ACK packet while not connected")
        else:
            logger.debug("Receiving ACK packet")
            self.ack_queue.put(packet)

    def handle_fin(self, packet):
        if self.status != CONNECTED:
            logger.error("Receiving FIN packet while not connected")
        else:
            logger.debug("Receiving FIN packet")
            self.socket.send_all(Packet.finack().encode())
            self.status = DISCONNECTING

    def handle_finack(self, packet):
        if self.status != DISCONNECTING:
            logger.error("Receiving FINACK packet while not disconnecting")
        else:
            logger.debug("Receiving FINACK packet")
            self.ack_queue.put(packet)

    def send(self, buffer):
        logger.debug(f"Sending buffer {buffer}")

        if self.status != CONNECTED:
            logger.error("Trying to send data while not connected")
        else:
            logger.debug("Sending data")
            packets = Packet.divide_buffer(buffer, 4)
            logger.debug("Fragmented buffer into %d packets" % len(packets))

            for packet in packets:
                logger.debug(
                    "Sending packet %d" % packet.headers["packet_number"]
                )
                while True:
                    self.socket.send_all(packet.encode())
                    try:
                        ack = self.ack_queue.get(timeout=10)
                        logger.debug("Received ACK packet")
                        break
                    except queue.Empty:
                        logger.error(
                            "Timeout waiting for ACK packet, sending again"
                        )

    def recv(self, buff_size):
        if self.status == NOT_CONNECTED:
            logger.error("Trying to receive data while not connected")
            raise Exception(
                "Trying to receive data while not connected (status"
                f" {self.status})"
            )
        else:
            logger.debug("Receiving data (buff_size %d)" % buff_size)
            info_body_bytes = self.info_bytestream.get_bytes(
                buff_size, timeout=1
            )
            if len(info_body_bytes) > 0:
                logger.debug(
                    "Received INFO packet (%d bytes)" % len(info_body_bytes)
                )
                return info_body_bytes
            else:
                return b""

    def close(self):
        if self.status == CONNECTED:
            logger.debug("Disconnecting")
            self.status = DISCONNECTING
            self.socket.send_all(Packet.fin().encode())
            logger.debug("Waiting for FINACK packet")
            while True:
                try:
                    finack = self.ack_queue.get(timeout=10)
                    logger.debug("Received FINACK packet")
                    break
                except queue.Empty:
                    logger.error("Timeout waiting for FINACK packet, sending again")
            self.status = DISCONNECTED
            self.socket.close()
        elif self.status == NOT_CONNECTED or self.status == DISCONNECTING:
            logger.debug("Closing socket")
            self.socket.close()
        else:
            logger.error("Trying to close socket while not connected")
            raise Exception(
                f"Trying to close socket while not connected (status {self.status})"
            )
