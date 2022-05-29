from numpy import info
from lib.mux_demux.mux_demux_stream import MuxDemuxStream
from lib.selective_repeat.packet import (
    Packet,
    Info,
    Connect,
    Fin,
    Finack,
    ACK,
    INFO,
    CONNECT,
    CONNACK,
    FIN,
    FINACK,
)
import socket
from lib.utils import MTByteStream
import threading
from loguru import logger
from .util import (
    AckNumberProvider,
    AckRegister,
    BlockAcker,
    SafeSendSocket,
    SocketStatus,
)
from .constants import (
    CONNECT_WAIT_TIMEOUT,
    CONNACK_WAIT_TIMEOUT,
    CONNECT_RETRIES,
    ACK_TIMEOUT,
    FIN_RETRIES,
    FIN_WAIT_TIMEOUT,
    FINACK_WAIT_TIMEOUT,
    CLOSING,
    MAX_SIZE,
    STOP_CHECK_INTERVAL,
    NOT_CONNECTED,
    CONNECTED,
    INITIAL_PACKET_NUMBER,
    WINDOW_SIZE,
)


class SRSocket:
    def __init__(
        self, window_size=WINDOW_SIZE, max_size=MAX_SIZE, buggyness_factor=0
    ):
        self.socket = None  # Solo usado para leer y cerrar el socket
        self.send_socket = SafeSendSocket()
        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.status = SocketStatus()
        self.buggyness_factor = buggyness_factor

        self.number_provider = AckNumberProvider(window_size)
        self.max_size = max_size
        self.upstream_channel = MTByteStream()
        self.ack_register = AckRegister()
        self.acker = BlockAcker(
            self.send_socket.send_all, self.upstream_channel
        )

    # Conectar tipo cliente
    def connect(self, addr):
        logger.debug(f"Connecting to {addr[0]}:{addr[1]}")
        self.socket = MuxDemuxStream(buggyness_factor=self.buggyness_factor)
        self.socket.connect(addr)
        self.send_socket.set_socket(self.socket)
        self.ack_register.enable_wait_first()
        # Esperar CONNACK
        self.__wait_connack(Connect())
        # Envío un INFO para confirmar recepción de CONNACK
        self.__send_info(Info(self.number_provider.get()))
        # Yo ya me puedo considerar conectado
        self.status.set_status(CONNECTED)
        logger.debug("Connected")
        self.packet_thread_handler.start()

    # Conectar tipo servidor
    def from_listener(self, mux_demux_socket):
        logger.debug("Creating new SRSocket from listener")
        self.socket = mux_demux_socket
        self.send_socket.set_socket(self.socket)
        self.socket.settimeout(CONNECT_WAIT_TIMEOUT)
        # Espero un connect
        connect = self.__wait_connect()

        # Mando connack y espero el primer info
        self.__wait_initial_info(connect.ack())
        self.status.set_status(CONNECTED)
        self.packet_thread_handler.start()

    def __wait_connect(self):
        self.socket.settimeout(CONNECT_WAIT_TIMEOUT)
        packet = Packet.read_from_stream(self.socket)
        if packet.type != CONNECT:
            logger.error(
                f"Received unexpected packet {packet} when initializing"
                " connection"
            )
            raise Exception(
                "Received unexpected packet {packet} when initializing"
                " connection"
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
                    f" ({packet}) while waiting for CONNACK"
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
        self.send_socket.send_all(connack.encode())
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
                    f"Received unexpected packet type ({packet}) while waiting"
                    " for initial info on connection startup)"
                )
            except (TimeoutError, socket.timeout):
                self.send_socket.send_all(connack.encode())
                logger.warning(
                    "Timed out waiting for initial info, retrying (attempt"
                    f" {i})"
                )
                continue
        raise TimeoutError("Could not confirm connection was established")

    def packet_handler(self):
        logger.debug("Packet handler started")
        self.socket.settimeout(STOP_CHECK_INTERVAL)

        while (
            self.status.get() == CONNECTED
        ) or self.ack_register.have_unacknowledged():
            try:
                packet = Packet.read_from_stream(self.socket)
            except (TimeoutError, socket.timeout):
                continue

            logger.info(f"Received packet of type {packet}")
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
                self.number_provider.push(packet.number())
                self.ack_register.acknowledge(packet)
            elif packet.type == FIN:
                self.status.set_status(CLOSING)
                self.__wait_finack_arrived(packet.ack())
            elif packet.type == FINACK:
                logger.warning("Received FINACK packet but a FIN wasn't sent")
            else:
                logger.error("Received unknown packet type")

        logger.debug("Packet handler stopping")

    def __wait_finack_arrived(self, finack):
        self.socket.settimeout(FIN_WAIT_TIMEOUT)
        self.send_socket.send_all(finack.encode())
        for i in range(FIN_RETRIES):
            try:
                packet = Packet.read_from_stream(self.socket)
                if packet.type == FIN:
                    logger.warning(
                        "Received FIN packet after sending FINACK, resending"
                        f" it (attempt {i})"
                    )
                    self.send_socket.send_all(finack.encode())
                    continue
                if packet.type == FINACK:
                    # Acá hay 3 opciones:
                    # 1) El otro tipo mandó un finack de la nada nada que ver,
                    # confiamos que no (en cuyo caso estaríamos cerrando igual)
                    # 2) Ambos cerraron a la vez, entonces ambos se pusieron a
                    # mandar finacks entonces si me llega uno listo, cerramos
                    # 3) Al otro le llegó mi finack y me manda otro que si
                    # llega me saca de este timeout largo, si no llega salgo
                    # igual pero más lento
                    return
                raise Exception(
                    "Received unexpected packet type"
                    f" ({packet}) while checking FINACK arrived"
                )
            except (TimeoutError, socket.timeout):
                logger.debug(
                    f"{FINACK_WAIT_TIMEOUT} seconds passed since FINACK was"
                    " sent and didn't receive another FIN or FINACK, assuming"
                    " it arrived successfully"
                )
                return
        logger.error(
            "Could not confirm connection was closed for the other end"
        )

    def close(self):
        self.ack_register.wait_first_acked()
        if self.status.get() == CLOSING:
            self.packet_thread_handler.join()
        else:
            self.status.set_status(CLOSING)
            self.packet_thread_handler.join()
            self.__wait_finack(Fin())

        self.socket.close()

    def __wait_finack(self, fin):
        self.socket.settimeout(FINACK_WAIT_TIMEOUT)
        self.send_socket.send_all(fin.encode())
        for i in range(FIN_RETRIES):
            try:
                packet = Packet.read_from_stream(self.socket)
                if packet.type == FINACK:
                    logger.info("Received FINACK")
                    # Sending finack to hopefully stop the receiver's
                    # timer sooner than it would normally do
                    self.send_socket.send_all(Finack().encode())
                    return
                if packet.type == FIN:
                    logger.debug(
                        "Both ends of connection sent FIN, switching to FINACK"
                    )
                    self.__wait_finack_arrived(packet.ack())
                    return
            except (TimeoutError, socket.timeout):
                self.send_socket.send_all(fin.encode())
                logger.warning(
                    f"Timed out waiting for finack, retrying (attempt {i})"
                )
                continue

        logger.error(
            "Could not confirm connection was closed for the other end"
        )

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
        self.ack_register.add_pending(packet)
        timer = threading.Timer(
            ACK_TIMEOUT,
            self.__check_ack,
            [packet, attempts],
        )
        timer.name = f"Timer-{packet.number()}-{attempts}"
        logger.info(f"Sending packet of type {packet}")
        timer.start()

    def send(self, buffer):
        if self.status.get() != CONNECTED:
            raise Exception("Socket is not connected or connection was closed")

        logger.debug(f"Sending buffer of length {len(buffer)}")
        packets = Info.from_buffer(buffer, self.max_size)
        logger.debug("Fragmented buffer into %d packets" % len(packets))

        self.ack_register.wait_first_acked()
        for packet in packets:
            packet.set_number(self.number_provider.get())
            self.__send_info(packet)

    def recv(self, buff_size, timeout=None):
        if self.status.get() == NOT_CONNECTED:
            raise Exception("Socket is not connected")

        logger.debug("Trying to receive data (buff_size %d)" % buff_size)

        try:
            info_body_bytes = self.upstream_channel.get_bytes(
                buff_size, timeout
            )
        except TimeoutError or socket.timeout as e:

            if self.status.get() == CLOSING:
                raise Exception(
                    "Connection was closed by the other end, reached end of"
                    " stream"
                ) from e
            raise e

        logger.debug("Received data (%d bytes)" % len(info_body_bytes))
        return info_body_bytes
