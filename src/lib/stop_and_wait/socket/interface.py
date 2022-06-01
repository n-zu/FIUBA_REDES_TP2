from abc import ABC, abstractmethod
from loguru import logger
import queue
import socket
import threading
import time

from ..exceptions import ProtocolError
from ..packet import PacketFactory, InfoPacket, AckPacket, FinPacket, FinackPacket


class SAWSocketInterface(ABC):
    PACKET_HANDLER_TIMEOUT = 0.5
    ACK_WAIT_TIMEOUT = 1.5
    SAFETY_TIME_BEFORE_DISCONNECT = 30
    FINACK_WAIT_TIMEOUT = 5
    MSS = 4

    def __init__(self, initial_state):
        self.socket = None
        self.socket_recv_lock = threading.RLock()
        self.socket_send_lock = threading.RLock()
        self.packet_thread_handler = None
        self.current_ack_number = 0
        self.current_info_number = 0

        self.timeout = None
        self.block = True

        self.state = initial_state
        self.state_lock = threading.RLock()

        self.ack_queue = queue.SimpleQueue()
        self.finack_queue = queue.SimpleQueue()

        self.info_bytestream = None

    @abstractmethod
    def handle_connect(self, packet):
        pass

    def recv_exact(self, buff_size):
        data = b''
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
        while True:
            time.sleep(0.5)
            with self.state_lock:
                if not self.state.can_recv() and not self.state.can_send():
                    logger.critical(f"Packet handler finished")
                    self.socket.close()
                    return
                with self.socket_recv_lock:
                    try:
                        packet = PacketFactory.read_from_stream(self.socket)
                    except socket.timeout:
                        continue
                    except ProtocolError as e:
                        logger.error(f"Protocol violation: {e} - Disconnecting")
                        self.state.set_disconnected()
                        break
                packet.be_handled_by(self)

        logger.critical(f"Packet handler finished")
        self.socket.close()

    def received_ack(self, packet):
        if packet.number == self.current_info_number:
            logger.info(
                f"Received expected ACK packet (Nº {packet.number})"
            )
            self.ack_queue.put(packet)
            self.current_info_number += 1
        else:
            logger.trace("Received ACK from retransmission, dropping")

    def send_ack_for(self, packet):
        if self.current_ack_number == packet.number:
            logger.info(f"Received expected INFO packet (Nº {packet.number}, data: {packet.body})")
            self.info_bytestream.put_bytes(packet.body)
            self.current_ack_number += 1
        else:
            logger.info(f"Received INFO retransmission (expected {self.current_ack_number}, got {packet.number}), dropping")
        with self.socket_send_lock:
            self.socket.send_all(bytes(AckPacket(packet.number)))

    def send_fin(self):
        logger.debug("Sending FIN")
        with self.socket_send_lock:
            self.socket.send_all(bytes(FinPacket()))

    def handle_info(self, packet):
        logger.debug(f"Received INFO packet while in state {self.state}")
        self.state.handle_info(packet)

    def handle_connack(self, packet):
        logger.debug("Received CONNACK packet while in state {self.state}")
        self.state.handle_connack(packet)

    def handle_ack(self, packet):
        logger.debug(f"Received ACK packet while in state {self.state}")
        self.state.handle_ack(packet)

    def handle_fin(self, packet):
        logger.debug(f"Received FIN packet while in state {self.state}")
        self.state.handle_fin(packet)

    def send_finack_for(self, _packet):
        logger.debug(f"Sending FINACK")
        with self.socket_send_lock:
            self.socket.send_all(bytes(FinackPacket()))

    def wait_for_fin_retransmission(self):
        self.socket.settimeout(self.SAFETY_TIME_BEFORE_DISCONNECT)
        while True:
            logger.info(f"Waiting some time for FIN retransmission")
            try:
                packet = PacketFactory.read_from_stream(self.socket)
                if packet.type == FinPacket.type:
                    logger.debug("Received FIN retransmission")
                    logger.info("Trying to take lock")
                    with self.socket_send_lock:
                        logger.info("Took lock")
                        self.socket.send_all(bytes(FinackPacket()))
                else:
                    logger.warning(f"Received packet distinct from FIN while waiting safety time ({packet}) (state: {self.state})")
            except socket.timeout:
                logger.debug("Finished waiting safety time for FIN retransmission")
                return

    def received_finack(self, packet):
        logger.success("Received FINACK")
        if self.finack_queue.empty():
            self.finack_queue.put(packet)

    def handle_finack(self, packet):
        logger.debug(f"Received FINACK packet while in state {self.state}")
        self.state.handle_finack(packet)

    def send_fin_reliably(self):
        old_timeout = self.socket.gettimeout()
        self.socket.settimeout(2)
        logger.info(f"Sending FIN reliably with timeout {self.socket.gettimeout()}")
        while self.finack_queue.empty():
            self.send_fin()
            try:
                packet = PacketFactory.read_from_stream(self.socket)
                packet.be_handled_by(self)
            except socket.timeout:
                logger.warning(f"Timeout waiting for FINACK while in state {self.state}, sending again")
                continue
        self.socket.settimeout(old_timeout)
        logger.success("Sent FIN reliably")

    def send_reliably(self, packet):
        while True:
            with self.state_lock:
                if self.state.can_send():
                    with self.socket_send_lock:
                        self.socket.send_all(bytes(packet))
                else:
                    raise ProtocolError(f"Cannot send packet while in state {self.state}")
            try:
                self.ack_queue.get(timeout=self.ACK_WAIT_TIMEOUT)
                logger.debug("Received ACK packet")
                break
            except queue.Empty:
                logger.warning(
                    f"Timeout waiting for ACK packet, sending again"
                )

    def send(self, buffer):
        logger.debug(f"Sending buffer {buffer}")

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
        try:
            info_body_bytes = self.info_bytestream.get_bytes(
                buff_size, timeout=self.timeout, block=self.block
            )
            if len(info_body_bytes) > 0:
                logger.debug(
                    f"Received INFO packet {len(info_body_bytes)} bytes)"
                )
            return info_body_bytes
        except socket.timeout:
            logger.debug("Received no INFO packet")
            return b""

    def close(self):
        logger.debug(f"Closing socket while in state {self.state}")
        with self.state_lock, self.socket_recv_lock:
            self.state.close()

    def settimeout(self, timeout):
        self.timeout = timeout

    def setblocking(self, block):
        self.block = block

