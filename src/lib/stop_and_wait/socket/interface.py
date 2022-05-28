import queue
import socket
import threading

from loguru import logger

from ..exceptions import ProtocolViolation
from ..packet import *


# No envie el CONNECT (si soy socket) ni lo recibi (si soy listener)
NOT_CONNECTED = "NOT_CONNECTED"
# Soy Socket de listener, mande el CONNACK y ya recibi info
# (confirma que el cliente recibio el CONNECT)
CONNECTING = "CONNECTING"
# Soy Socket de listener, y recibi el CONNECT
CONNECTED = "CONNECTED"
# Mande FIN, y recibi FINACK
FIN_SENT = "FIN_SENT"
# Recibi FIN y mande FINACK (tal vez no fue recibido)
FIN_RECV = "FIN_RECEIVED"
# Desconectado
DISCONNECTED = "DISCONNECTED"

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


class SAWSocketInterface:
    PACKET_HANDLER_TIMEOUT = 1
    ACK_WAIT_TIMEOUT = 0.1
    SAFETY_TIME_BEFORE_DISCONNECT = 5
    FINACK_WAIT_TIMEOUT = 0.5
    MTU = 4

    def __init__(self):
        self.socket = None
        self.packet_thread_handler = None
        self.next_packet_number_to_recv = 0
        self.next_packet_number_to_send = 0

        self.timeout = None
        self.block = True

        self.is_from_listener = None
        self.status = MTStatus()

        self.ack_queue = queue.Queue()
        self.finack_queue = queue.Queue()

        self.info_bytestream = None
        self.stop_event = threading.Event()

    @abstractmethod
    def handle_connect(self, packet):
        pass

    def packet_handler(self):
        logger.debug("Packet handler started")
        self.socket.settimeout(self.PACKET_HANDLER_TIMEOUT)
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
                self.status.set(DISCONNECTED)
                self.close()
                return

    def handle_info(self, packet):
        if self.status.is_equal(NOT_CONNECTED):
            raise ProtocolViolation("Received INFO packet while not connected")
        elif self.status.is_equal(CONNECTING):
            # Confirmo que ya se recibio el CONNACK
            logger.debug(
                "Received INFO packet while connecting, now fully connected"
            )
            self.status.set(CONNECTED)

        if self.next_packet_number_to_recv == packet.number:
            logger.debug(
                f"Received expected INFO packet (Nº {packet.number}) (data:"
                f" {packet.body})"
            )
            self.socket.send_all(bytes(AckPacket()))
            self.info_bytestream.put_bytes(packet.body)
            self.next_packet_number_to_recv += 1
        # TODO: hay que chequear que sea MENOR, porque puede pasar que el paquete
        # se demore en la red
        # Tambien hay que reiniciar el contador cada cierto tiempo
        elif packet.number == self.next_packet_number_to_recv - 1:
            logger.debug(
                "Received INFO retransmission. Expecting"
                f" {self.next_packet_number_to_recv}, received {packet.number}"
            )
            self.socket.send_all(bytes(AckPacket()))
        else:
            logger.error(
                "Received unexpected INFO packet, dropping (expected %s,"
                " received %s)"
                % (
                    self.next_packet_number_to_recv,
                    packet.headers["packet_number"],
                )
            )

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
            logger.error(
                "Receiving ACK packet while not connected (status:"
                f" {self.status})"
            )
        else:
            logger.debug("Receiving ACK packet")
            self.ack_queue.put(packet)

    def handle_fin(self, _packet):
        logger.debug("Received FIN packet")

        if self.status.is_equal(DISCONNECTED):
            logger.error(
                f"Received FIN packet but it was already disconnected"
            )
        elif self.status.is_equal(FIN_SENT):
            logger.debug("Sending FINACK packet and waiting before disconnecting")
            self.socket.send_all(bytes(FinackPacket()))
            self.wait_for_fin_retransmission()
            self.stop_event.set()
            self.status.set(DISCONNECTED)
            self.socket.close()

        elif self.status.is_equal(CONNECTED):
            logger.debug("Sending FINACK packet")
            self.socket.send_all(bytes(FinackPacket()))
            self.status.set(FIN_RECV)

        elif self.status.is_equal(FIN_RECV):
            logger.debug("Sending FINACK retransmission")
            self.socket.send_all(bytes(FinackPacket()))
        else:
            logger.error(f"Received FIN packet while in status {self.status}")
            self.status.set(DISCONNECTED)
            self.stop_event.set()
            self.socket.close()

    def wait_for_fin_retransmission(self):
        while True:
            try:
                self.socket.settimeout(self.SAFETY_TIME_BEFORE_DISCONNECT)
                packet = PacketFactory.read_from_stream(self.socket)
                if packet.type == FIN:
                    logger.debug("Received FIN retransmission")
                    self.socket.send_all(bytes(FinackPacket()))
                else:
                    logger.error("Received packet distinct from FIN while waiting safety time")
                    self.status.set(DISCONNECTED)
            except socket.timeout:
                logger.info("Finished waiting safety time for FIN retransmission")
                return

    def handle_finack(self, packet):
        if self.status.is_equal(FIN_SENT):
            logger.debug("Received FINACK packet")
            self.finack_queue.put(packet)
        else:
            logger.error("Received FINACK packet while not waiting for it")
            self.status.set(DISCONNECTED)
            self.close()

    def send(self, buffer):
        logger.debug(f"Sending buffer {buffer}")

        if not self.status.is_equal(CONNECTED) and not self.status.is_equal(
            CONNECTING
        ):
            logger.error("Trying to send data while not connected")
        else:
            logger.debug("Sending data")
            packets = InfoPacket.split(
                self.MTU, buffer, initial_number=self.next_packet_number_to_send
            )
            logger.debug("Fragmented buffer into %d packets" % len(packets))
            self.next_packet_number_to_send += len(packets)

            for packet in packets:
                logger.debug(
                    f"Sending packet Nº {packet.number}, data: {packet.body}"
                )
                while True:
                    self.socket.send_all(bytes(packet))
                    try:
                        ack = self.ack_queue.get(timeout=self.ACK_WAIT_TIMEOUT)
                        logger.debug("Received ACK packet")
                        break
                    except queue.Empty:
                        logger.warning(
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
            try:
                info_body_bytes = self.info_bytestream.get_bytes(
                    buff_size, timeout=self.timeout, block=self.block
                )
                if len(info_body_bytes) > 0:
                    logger.debug(
                        "Received INFO packet (%d bytes)"
                        % len(info_body_bytes)
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
            self.status.set(FIN_SENT)
            logger.debug("Waiting for FINACK packet")
            while True:
                self.socket.send_all(bytes(FinPacket()))
                try:
                    self.finack_queue.get(timeout=self.FINACK_WAIT_TIMEOUT)
                    break
                except queue.Empty:
                    logger.warning(
                        "Timeout waiting for FINACK packet, sending again"
                    )
        elif self.status.is_equal(FIN_RECV):
            logger.debug("Disconnecting")
            logger.debug("Waiting for FINACK packet")
            self.status.set(FIN_SENT)
            while True:
                self.socket.send_all(bytes(FinPacket()))
                try:
                    self.finack_queue.get(timeout=self.FINACK_WAIT_TIMEOUT)
                    break
                except queue.Empty:
                    logger.warning(
                        "Timeout waiting for FINACK packet, sending again"
                    )
            self.status.set(DISCONNECTED)
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
