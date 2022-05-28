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


class SAWSocketInterface(ABC):
    PACKET_HANDLER_TIMEOUT = 1
    ACK_WAIT_TIMEOUT = 0.1
    SAFETY_TIME_BEFORE_DISCONNECT = 5
    FINACK_WAIT_TIMEOUT = 2
    MTU = 4

    def __init__(self, initial_state):
        self.socket = None
        self.packet_thread_handler = None
        self.next_packet_number_to_recv = 0
        self.next_packet_number_to_send = 0

        self.timeout = None
        self.block = True

        self.state = initial_state

        self.ack_queue = queue.Queue()
        self.finack_queue = queue.Queue()

        self.info_bytestream = None

    @abstractmethod
    def handle_connect(self, packet):
        pass

    def set_state(self, state):
        self.state = state

    def stop(self):
        self.state.set_disconnected()

    def packet_handler(self):
        logger.debug("Packet handler started")
        self.socket.settimeout(self.PACKET_HANDLER_TIMEOUT)
        self.socket.setblocking(True)
        while self.state.can_send() or self.state.can_recv():
            try:
                packet = PacketFactory.read_from_stream(self.socket)
                logger.debug("Handling packet %s" % packet)
                packet.be_handled_by(self)
            except socket.timeout:
                pass
            except ProtocolViolation:
                logger.error("Protocol violation, closing connection")
                self.state.set_disconnected()
                self.close()
                return
        self.socket.close()


    def received_ack(self, packet):
        if packet.number == self.next_packet_number_to_send:
            logger.debug(
                f"Received expected ACK packet (Nº {packet.number})"
            )
            self.ack_queue.put(packet)
            self.next_packet_number_to_send += 1
        else:
            logger.debug("Received ACK from retransmission, dropping")

    def send_ack_for(self, packet):
        if self.next_packet_number_to_recv == packet.number:
            self.info_bytestream.put_bytes(packet.body)
            self.next_packet_number_to_recv += 1
        else:
            logger.warning(f"Received INFO retransmission (expected {self.next_packet_number_to_recv}, got {packet.number}), dropping")
        self.socket.send_all(bytes(AckPacket(packet.number)))

    def send_fin(self):
        logger.debug("Sending FIN")
        while True:
            self.socket.send_all(bytes(FinPacket()))
            try:
                finack = self.finack_queue.get(timeout=self.FINACK_WAIT_TIMEOUT)
                logger.debug("Received FINACK from queue")
                return finack
            except queue.Empty:
                logger.debug("Timeout waiting for FINACK, sending again")

    def handle_info(self, packet):
        logger.debug(f"Received INFO packet while in state {self.state}")
        self.state.handle_info(packet)

    def handle_connack(self, packet):
        logger.debug("Received CONNACK packet")
        self.state.handle_connack(packet)

    def handle_ack(self, packet):
        logger.debug("Received ACK packet")
        self.state.handle_ack(packet)

    def handle_fin(self, packet):
        logger.debug(f"Received FIN packet while in state {self.state}")
        self.state.handle_fin(packet)

    def send_finack_for(self, packet):
        self.socket.send_all(bytes(FinackPacket()))

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
            except socket.timeout:
                logger.info("Finished waiting safety time for FIN retransmission")
                return

    def received_finack(self, packet):
        logger.success("Received FINACK")
        self.finack_queue.put(packet)

    def handle_finack(self, packet):
        logger.debug(f"Received FINACK packet while in state {self.state}")
        self.state.handle_finack(packet)

    def send(self, buffer):
        logger.debug(f"Sending buffer {buffer}")

        if self.state.can_send():
            packets = InfoPacket.split(
                self.MTU, buffer, initial_number=self.next_packet_number_to_send
            )
            logger.debug("Fragmented buffer into %d packets" % len(packets))

            for packet in packets:
                logger.debug(
                    f"Sending packet Nº {packet.number}, data: {packet.body}"
                )
                while True:
                    self.socket.send_all(bytes(packet))
                    try:
                        self.ack_queue.get(timeout=self.ACK_WAIT_TIMEOUT)
                        logger.debug("Received ACK packet")
                        break
                    except queue.Empty:
                        logger.warning(
                            "Timeout waiting for ACK packet, sending again"
                        )
        else:
            raise Exception("Cannot send while in state %s" % self.state)

    def recv(self, buff_size):
        if self.state.can_recv():
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
        else:
            return b""
            #raise Exception("Cannot recv while in state %s" % self.state)

    def close(self):
        logger.debug(f"Closing socket while in state {self.state}")
        self.state.close()

    def settimeout(self, timeout):
        self.timeout = timeout

    def setblocking(self, block):
        self.block = block

