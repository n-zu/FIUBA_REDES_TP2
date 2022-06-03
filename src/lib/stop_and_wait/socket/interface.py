from abc import ABC, abstractmethod
from loguru import logger
import queue
import socket
import threading
import time

from ..exceptions import ProtocolError, EndOfStream
from ..packet import (
    PacketFactory,
    InfoPacket,
    AckPacket,
    FinPacket,
    FinackPacket,
)

SEND_RETRIES = 50

class SAWSocketInterface(ABC):
    PACKET_HANDLER_TIMEOUT = 0.1
    ACK_WAIT_TIMEOUT = 1.5
    SAFETY_TIME_BEFORE_DISCONNECT = 7
    FINACK_WAIT_TIMEOUT = 1.5
    MSS = 128
    CLOSED_CHECK_INTERVAL = 1

    def __init__(self, initial_state):
        self.socket = None
        self.packet_thread_handler = None
        self.current_ack_number = 0
        self.current_info_number = 0

        self.timeout = None
        self.block = True

        self.state = initial_state
        self.state_lock = threading.RLock()

        self.ack_queue = queue.SimpleQueue()
        self.finack_received = threading.Event()

        self.info_bytestream = None

    @abstractmethod
    def handle_connect(self, packet):
        pass

    def recv_exact(self, buff_size):
        data = b""
        while len(data) < buff_size:
            data += self.recv(buff_size - len(data))
        return data

    def set_state(self, state):
        self.state = state

    def stop(self):
        with self.state_lock:
            self.state.set_disconnected()

    def packet_handler(self):
        logger.debug("Packet handler started")
        self.socket.settimeout(self.PACKET_HANDLER_TIMEOUT)
        self.socket.setblocking(True)
        for i in range(SEND_RETRIES):
            time.sleep(0.1)
            with self.state_lock:
                if not self.state.can_recv() and not self.state.can_send():
                    self.socket.close()
                    return
                try:
                    packet = self.socket.read_packet()
                except socket.timeout:
                    continue
                except ProtocolError as e:
                    logger.error(f"Protocol violation: {e}")
                    break
                logger.debug(f"Received packet {packet}")
                packet.be_handled_by(self)
        logger.info("Disconnecting")
        self.state.set_disconnected()
        self.socket.close()

    def received_ack(self, packet):
        if packet.number == self.current_info_number:
            logger.info(f"Received expected ACK packet (Nº {packet.number})")
            self.ack_queue.put(packet)
            self.current_info_number += 1
        else:
            logger.trace("Received ACK from retransmission, dropping")

    def send_ack_for(self, packet):
        if self.current_ack_number == packet.number:
            logger.info(
                f"Received expected INFO packet (Nº {packet.number}, data:"
                f" {packet.body})"
            )
            self.info_bytestream.put_bytes(packet.body)
            self.current_ack_number += 1
        else:
            logger.info(
                "Received INFO retransmission (expected"
                f" {self.current_ack_number}, got {packet.number}), dropping"
            )
        self.socket.send_all(bytes(AckPacket(packet.number)))

    def handle_info(self, packet):
        self.state.handle_info(packet)

    def handle_connack(self, packet):
        self.state.handle_connack(packet)

    def handle_ack(self, packet):
        self.state.handle_ack(packet)

    def handle_fin(self, packet):
        self.state.handle_fin(packet)

    def send_finack_for(self, _packet):
        self.socket.send_all(bytes(FinackPacket()))

    def wait_for_fin_retransmission(self):
        self.socket.settimeout(self.SAFETY_TIME_BEFORE_DISCONNECT)
        while True:
            logger.info("Waiting some time for FIN retransmission")
            try:
                packet = PacketFactory.read_from_stream(self.socket)
                if packet.type == FinPacket.type:
                    logger.debug("Received FIN retransmission")
                    self.socket.send_all(bytes(FinackPacket()))
                else:
                    logger.warning(
                        "Received packet distinct from FIN while waiting"
                        f" safety time ({packet}) (state: {self.state})"
                    )
            except socket.timeout:
                logger.debug(
                    "Finished waiting safety time for FIN retransmission"
                )
                return

    def received_finack(self, _packet):
        self.finack_received.set()

    def handle_finack(self, packet):
        self.state.handle_finack(packet)

    def send_fin_reliably(self):
        old_timeout = self.socket.gettimeout()
        self.socket.settimeout(2)
        logger.info(
            f"Sending FIN reliably with timeout {self.socket.gettimeout()}"
        )
        while not self.finack_received.is_set():
            self.socket.send_all(bytes(FinPacket()))
            try:
                packet = PacketFactory.read_from_stream(self.socket)
                packet.be_handled_by(self)
            except socket.timeout:
                logger.warning(
                    f"Timeout waiting for FINACK while in state {self.state},"
                    " sending again"
                )
                continue
        self.socket.settimeout(old_timeout)
        logger.success("Sent FIN reliably")

    def send_reliably(self, packet):
        while True:
            with self.state_lock:
                if self.state.can_send():
                    self.socket.send_all(bytes(packet))
                else:
                    raise ProtocolError(
                        f"Cannot send packet while in state {self.state}"
                    )
            try:
                self.ack_queue.get(timeout=self.ACK_WAIT_TIMEOUT)
                logger.debug("Received ACK packet")
                break
            except queue.Empty:
                logger.warning("Timeout waiting for ACK packet, sending again")

    def send(self, buffer):
        logger.debug(f"Sending buffer of length {len(buffer)}")

        packets = InfoPacket.split(
            self.MSS, buffer, initial_number=self.current_info_number
        )
        logger.debug(f"Fragmented buffer into {len(packets)} packets")

        for packet in packets:
            logger.debug(
                f"Sending packet Nº {packet.number}, data: {packet.body}"
            )
            self.send_reliably(packet)

    def recv(self, buff_size):
        logger.debug(f"Trying to receive data (buff_size = {buff_size})")

        start = time.time()
        while True:
            if self.state.can_recv():
                try:
                    info_body_bytes = self.info_bytestream.get_bytes(
                        buff_size, self.CLOSED_CHECK_INTERVAL
                    )
                    logger.trace(
                        f"Received data ({len(info_body_bytes)} bytes)"
                    )
                    return info_body_bytes
                except socket.timeout:
                    if not self.block and time.time() - start > self.timeout:
                        raise
            else:
                raise EndOfStream("Connection was closed")

    def close(self):
        logger.debug("Closing socket")
        # Si falla agregar socket_recv_lock
        with self.state_lock:
            self.state.close()

    def settimeout(self, timeout):
        self.timeout = timeout

    def setblocking(self, block):
        self.block = block
