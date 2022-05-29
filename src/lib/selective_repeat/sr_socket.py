from lib.mux_demux.mux_demux_stream import MuxDemuxStream
from lib.selective_repeat.packet import (
    Packet,
    Info,
    Connect,
    ACK,
    INFO,
    CONNECT,
    CONNACK,
)
import socket
from lib.utils import MTByteStream
import threading
from loguru import logger
from .util import AckNumberProvider, AckRegister, BlockAcker, SafeSendSocket
from .constants import (
    CONNECT_WAIT_TIMEOUT,
    CONNACK_WAIT_TIMEOUT,
    CONNECT_RETRIES,
    ACK_TIMEOUT,
    MAX_SIZE,
    STOP_CHECK_INTERVAL,
    NOT_CONNECTED,
    CONNECTED,
    INITIAL_PACKET_NUMBER,
)


class SRSocket:
    def __init__(self):
        self.socket = None  # Solo usado para leer y cerrar el socket
        self.send_socket = SafeSendSocket()
        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.is_from_listener = None
        self.status = NOT_CONNECTED

        self.number_provider = AckNumberProvider()
        self.upstream_channel = MTByteStream()
        self.stop_flag = threading.Event()
        self.ack_register = AckRegister()
        self.acker = BlockAcker(
            self.send_socket.send_all, self.upstream_channel
        )

    # Conectar tipo cliente
    def connect(self, addr):
        self.is_from_listener = False
        logger.debug(f"Connecting to {addr[0]}:{addr[1]}")
        self.socket = MuxDemuxStream()
        self.socket.connect(addr)
        self.send_socket.set_socket(self.socket)
        # Esperar CONNACK
        self.__wait_connack(Connect())
        # Envío un INFO para confirmar recepción de CONNACK
        self.__send_info(Info(self.number_provider.get()))

        # Yo ya me puedo considerar conectado
        self.status = CONNECTED
        logger.debug("Connected")
        self.packet_thread_handler.start()

    # Conectar tipo servidor
    def from_listener(self, mux_demux_socket):
        logger.debug("Creating new SRSocket from listener")
        self.is_from_listener = True
        self.socket = mux_demux_socket
        self.send_socket.set_socket(self.socket)
        self.socket.settimeout(CONNECT_WAIT_TIMEOUT)
        try:
            # Espero un connect
            connect = self.__wait_connect()
        except TimeoutError or socket.timeout:
            logger.debug("Timed out waiting for CONNECT packet")

        # Mando connack y espero el primer info
        self.__wait_initial_info(connect.ack())
        self.status = CONNECTED
        self.packet_thread_handler.start()

    def __wait_connect(self):
        self.socket.settimeout(CONNECT_WAIT_TIMEOUT)
        packet = Packet.read_from_stream(self.socket)
        if packet.type != CONNECT:
            raise Exception(
                "Received unexpected packet type when initializing connection"
            )
        return packet

    def __wait_connack(self, connect):
        self.socket.settimeout(CONNACK_WAIT_TIMEOUT)
        self.send_socket.send_all(connect.encode())
        for i in range(CONNECT_RETRIES):
            try:
                packet = Packet.read_from_stream(self.socket)
                if packet.type == CONNACK:
                    return
                raise Exception(
                    "Received unexpected packet type"
                    f" ({Packet.get_type_from_byte(packet.type)}) while"
                    " waiting for CONNACK"
                )
            except (TimeoutError, socket.timeout):
                self.send_socket.send_all(connect.encode())
                logger.warning(
                    f"Timed out waiting for connack, retrying (attempt {i})"
                )
                continue
        raise TimeoutError("Could not confirm connection was established")

    def __wait_initial_info(self, connack):
        self.socket.settimeout(CONNACK_WAIT_TIMEOUT)
        for i in range(CONNECT_RETRIES):
            try:
                packet = Packet.read_from_stream(self.socket)
                if packet.type == CONNECT:
                    # Asumo que no le llego mi connack
                    continue
                if packet.type == INFO:
                    self.acker.received(packet)
                    if packet.number() != INITIAL_PACKET_NUMBER:
                        continue
                    return
                raise Exception(
                    "Received unexpected packet type"
                    f" ({Packet.get_type_from_byte(packet.type)}) while"
                    " waiting for initial info on connection startup)"
                )
            except (TimeoutError, socket.timeout):
                self.send_socket.send_all(connack.encode())
                logger.warning(
                    "Timed out waiting for initial info, retrying (attempt"
                    f" {i})"
                )
                continue
        raise TimeoutError("Could not confirm connection was established")

    def close(self):
        self.stop_flag.set()
        self.packet_thread_handler.join()
        self.socket.close()

    def packet_handler(self):
        logger.debug("Packet handler started")
        self.socket.settimeout(STOP_CHECK_INTERVAL)

        while (
            not self.stop_flag.is_set()
        ) or self.ack_register.have_unacknowledged():
            try:
                packet = Packet.read_from_stream(self.socket)
            except (TimeoutError, socket.timeout):
                continue

            logger.info(f"Received packet of type {packet.description()}")
            if packet.type == CONNECT:
                logger.warning(
                    "Received CONNECT packet while already connected."
                )
            elif packet.type == CONNACK:
                logger.warning(
                    "Received CONNACK packet while already connected."
                )
            elif packet.type == INFO:
                self.acker.received(packet)
            elif packet.type == ACK:
                self.number_provider.push()
                self.ack_register.acknowledge(packet)
            else:
                logger.error("Received unknown packet type")

    def __check_ack(self, packet, send_attempt):
        if self.ack_register.check_acknowledged(packet):
            return

        logger.warning(
            f"Packet with number {packet.number()} not acknowledged on time,"
            f" resending it (attempt {send_attempt})"
        )
        self.__send_info(packet, send_attempt + 1)

    def __send_info(self, packet, attempts=0):
        self.send_socket.send_all(packet.encode())
        timer = threading.Timer(
            ACK_TIMEOUT,
            self.__check_ack,
            [packet, attempts],
        )
        timer.name = f"Timer-{packet.number()}-{attempts}"
        logger.info(f"Sending packet of type {packet.description()}")
        timer.start()

    def send(self, buffer):
        logger.debug(f"Sending buffer of length {len(buffer)}")
        if self.status != CONNECTED:
            logger.error("Trying to send data while not connected")
        else:
            logger.debug("Sending data")
            packets = Info.from_buffer(buffer, MAX_SIZE)
            logger.debug("Fragmented buffer into %d packets" % len(packets))

            for packet in packets:
                packet.set_number(self.number_provider.get())
                self.ack_register.add_pending(packet)
                logger.debug(
                    "Added pending acknowledgement for packet"
                    f" {packet.number()}"
                )
                self.__send_info(packet)

    def recv(self, buff_size, timeout=None):
        logger.debug("Trying to receive data (buff_size %d)" % buff_size)
        info_body_bytes = self.upstream_channel.get_bytes(buff_size, timeout)
        logger.debug("Received data (%d bytes)" % len(info_body_bytes))
        return info_body_bytes
