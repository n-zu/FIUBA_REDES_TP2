from queue import Empty
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
    CLOSED,
    CLOSED_CHECK_INTERVAL,
    CONNECT_WAIT_TIMEOUT,
    CONNACK_WAIT_TIMEOUT,
    CONNECT_RETRIES,
    ACK_TIMEOUT,
    ACK_RETRIES,
    FIN_RETRIES,
    FIN_WAIT_TIMEOUT,
    FINACK_WAIT_TIMEOUT,
    MAX_SIZE,
    PEER_CLOSED,
    STOP_CHECK_INTERVAL,
    NOT_CONNECTED,
    CONNECTED,
    FORCED_CLOSING,
    INITIAL_PACKET_NUMBER,
    WINDOW_SIZE,
)
import time


class SRSocket:
    def __init__(self, window_size=WINDOW_SIZE, max_size=MAX_SIZE):
        self.socket = None  # Solo usado para leer y cerrar el socket
        self.send_socket = SafeSendSocket()
        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.status = SocketStatus()

        self.number_provider = AckNumberProvider(window_size)
        self.max_size = max_size
        self.upstream_channel = MTByteStream()
        self.ack_register = AckRegister()
        self.acker = BlockAcker(
            self.send_socket.send_all, self.upstream_channel
        )

    def set_window_size(self, window_size):
        self.number_provider.set_window_size(window_size)

    # Conectar tipo cliente
    def connect(self, addr, buggyness_factor=0):
        if self.status.get() != NOT_CONNECTED:
            raise Exception("Socket has already been connected")

        logger.debug(f"Connecting to {addr[0]}:{addr[1]}")
        self.socket = MuxDemuxStream(buggyness_factor=buggyness_factor)
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
        if self.status.get() != NOT_CONNECTED:
            raise Exception("Socket has already been connected")

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
            logger.error(f"Received  {packet}, Expecting CONNECT")
            raise Exception(f"Received  {packet}, Expecting CONNECT")
        return packet

    def __wait_connack(self, connect):
        self.socket.settimeout(CONNACK_WAIT_TIMEOUT)
        self.send_socket.send_all(connect.encode())
        for i in range(CONNECT_RETRIES):
            try:
                packet = Packet.read_from_stream(self.socket)
                if packet.type == CONNACK:
                    return
                logger.error(f"Received  {packet}, Expecting CONNACK")
                raise Exception(f"Received  {packet}, Expecting CONNACK")
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

        while not self.status.is_closed() or (
            self.ack_register.have_unacknowledged()
            and self.status.get() != FORCED_CLOSING
        ):
            try:
                packet = Packet.read_from_stream(self.socket)
            except (TimeoutError, socket.timeout):
                continue

            logger.info(f"Received packet of type {packet}")
            packet.be_handled_by(self)

        logger.debug("Packet handler stopping")

    def handle_connect(self, connect):
        logger.warning("Received CONNECT packet while already connected.")

    def handle_connack(self, connack):
        logger.warning("Received CONNACK packet while already connected.")

    def handle_info(self, info):
        self.acker.received(info)

    def handle_ack(self, ack):
        self.number_provider.push(ack.number())
        self.ack_register.acknowledge(ack)

    def handle_fin(self, fin):
        self.status.set_status(PEER_CLOSED)
        self.__wait_finack_arrived(fin.ack())
        self.ack_register.stop()

    def handle_finack(self, finack):
        logger.warning("Received FINACK packet but a FIN wasn't sent")

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
                logger.warning(
                    "Received unexpected packet type ({packet})"
                    f" while checking FINACK arrived, retrying (attempt {i})"
                )
                if packet.type == ACK:
                    # Un ack que quedó colgado
                    self.number_provider.push(packet.number())
                    self.ack_register.acknowledge(packet)
            except (TimeoutError, socket.timeout):
                logger.debug(
                    f"{FIN_WAIT_TIMEOUT} seconds passed since FINACK was"
                    " sent and didn't receive another FIN or FINACK, assuming"
                    " it arrived successfully"
                )
                return
        logger.warning(
            "Could not confirm connection was closed for the other end"
        )

    def __force_close(self):
        if self.status.get() == FORCED_CLOSING:
            logger.trace("FORCED_CLOSING already in progress")
            return

        self.status.set_status(FORCED_CLOSING)
        self.send_socket.send_all(Packet(FIN).encode())
        logger.error("Fatal error, ending connection abruptly")
        self.packet_thread_handler.join()
        self.socket.close()

    def close(self):
        self.ack_register.wait_first_acked()
        if self.status.get() == CLOSED:
            return

        if self.status.get() == PEER_CLOSED:
            self.packet_thread_handler.join()
        else:
            self.status.set_status(CLOSED)
            self.packet_thread_handler.join()
            # Peer may have closed before I could
            # join this thread
            if self.status.get() != PEER_CLOSED:
                self.__wait_finack(Fin())

        self.socket.close()
        self.status.set_status(CLOSED)

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
                if packet.type == INFO:
                    # Algun info que no le llegó mi ack o le quedó colgado
                    self.acker.received(packet)
                    continue
            except (TimeoutError, socket.timeout):
                self.send_socket.send_all(fin.encode())
                logger.warning(
                    f"Timed out waiting for finack, retrying (attempt {i})"
                )
                continue

        logger.warning(
            "Could not confirm connection was closed for the other end"
        )

    def __check_ack(self, packet, send_attempt):
        if self.ack_register.check_acknowledged(packet):
            return

        if self.status.get() == FORCED_CLOSING:
            return

        if send_attempt > ACK_RETRIES:
            return self.__force_close()

        logger.warning(
            f"Packet with number {packet.number()} not acknowledged on time,"
            f" resending it (attempt {send_attempt})"
        )
        logger.debug(f"Resend Attemp {send_attempt}")
        self.__send_info(packet, send_attempt + 1)

    def __send_info(self, packet, attempts=0):

        if self.status.get() == FORCED_CLOSING:
            logger.trace("FORCED_CLOSING in progress")
            return

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

        packets = iter(packets)
        packet = next(packets)
        while True:
            try:
                packet.set_number(
                    self.number_provider.get(timeout=CLOSED_CHECK_INTERVAL)
                )
                self.__send_info(packet)
                packet = next(packets)
            except (TimeoutError, socket.timeout, Empty) as e:
                # Connection may have been closed when we were waiting
                # for a packet number
                if self.status.is_closed():
                    raise Exception("Connection was closed during send") from e
            except StopIteration:
                break

    def recv(self, buff_size, timeout=None):
        if self.status.get() == NOT_CONNECTED:
            raise Exception("Socket is not connected")
        logger.trace("Trying to receive data (buff_size %d)" % buff_size)
        start = time.time()

        while True:
            try:
                info_body_bytes = self.upstream_channel.get_bytes(
                    buff_size, CLOSED_CHECK_INTERVAL
                )
                logger.trace("Received data (%d bytes)" % len(info_body_bytes))
                return info_body_bytes
            except (TimeoutError, socket.timeout) as e:
                if self.status.is_closed():
                    raise EndOfStream("Connection was closed") from e
                if timeout and time.time() - start > timeout:
                    raise

    # If it times out or there is an end of stream, it returns
    # the data read so far
    def recv_exact(self, size, timeout=None):
        buffer = b""
        start = time.time()
        while len(buffer) < size and (
            not timeout or time.time() - start < timeout
        ):
            buffer += self.recv(size - len(buffer), timeout)

        if len(buffer) == 0:
            raise TimeoutError("No data received")
        return buffer


class EndOfStream(Exception):
    pass
