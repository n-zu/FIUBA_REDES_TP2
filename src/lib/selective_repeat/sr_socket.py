from lib.mux_demux.mux_demux_stream import MuxDemuxStream
from lib.selective_repeat.packet import (
    Packet,
    Info,
    Ack,
    Connect,
    Connack,
    ACK,
    INFO,
    CONNECT,
    CONNACK,
)
import queue
import socket
from lib.utils import MTByteStream
import threading
from loguru import logger

CONNACK_WAIT_TIMEOUT = 1.5
CONNACK_RETRIES = 3

ACK_TIMEOUT = 1.5

MAX_SIZE = 1024

STOP_CHECK_INTERVAL = 0.1

# No envie el CONNECT (si soy socket) ni lo recibi (si soy listener)
NOT_CONNECTED = "NOT_CONNECTED"
# Soy Socket de listener, mande el CONNACK y ya recibi info
# (confirma que el cliente recibio el CONNECT)
CONNECTING = "CONNECTING"
# Soy Socket de listener, y recibi el CONNECT
CONNECTED = "CONNECTED"

# Siempre se debe cumplir WINDOW_SIZE < ACK_NUMBERS / 2
WINDOW_SIZE = 100
ACK_NUMBERS = 4294967296


# Cuenta los paquetes on-flight y bloquea el get() hasta que haya
# espacio en la window
class AckNumberProvider:
    def __init__(self):
        self.next = WINDOW_SIZE
        self.channel = queue.SimpleQueue()
        for i in range(WINDOW_SIZE):
            self.channel.put(i)

    def get(self):
        n = self.channel.get()
        return n

    def push(self):
        self.channel.put(self.next)
        self.next += 1
        self.next %= ACK_NUMBERS


def gt_packets(packet_number, other_packet_number):
    # Si entra al if, esta wrappeando los acks (ej.: 4294967295 < 10,
    # porque me tiene que llegar el ack del 4294967295 antes que el del 10)
    if packet_number + ACK_NUMBERS - other_packet_number <= ACK_NUMBERS / 2:
        return True

    return packet_number > other_packet_number


# Hace ACK a los INFO recibidos y los envia por la queue
class BlockAcker:
    def __init__(self, sender, upstream_channel):
        self.last_received = None
        self.blocks = {}
        self.sender = sender
        self.upstream_channel = upstream_channel

    def __send_stored(self):
        i = self.last_received
        while i in self.blocks:
            self.upstream_channel.put_bytes(self.blocks[i].body())
            self.blocks.pop(i)
            self.last_received = i
            i += 1

    def received(self, packet):

        if (
            self.last_received is None
            or (self.last_received + 1) % ACK_NUMBERS == packet.number()
        ):
            self.last_received = packet.number()
            self.blocks[packet.number()] = packet
            self.__send_stored()
        elif gt_packets(packet.number(), self.last_received):
            self.blocks[packet.number()] = packet

        logger.info(f"Sending ACK for packet {packet.description()}")
        self.sender(packet.ack().encode())


class AckRegister:
    def __init__(self):
        self.lock = threading.Lock()
        self.unacknowledged = set()

    def add_pending(self, packet):
        with self.lock:
            self.unacknowledged.add(packet.number())

    def acknowledge(self, packet):
        with self.lock:
            self.unacknowledged.remove(packet.number())

    # Devuelve true si fue recibió Ack, false sino
    def pop_acknowledged(self, packet):
        with self.lock:
            return not packet.number() in self.unacknowledged

    def have_unacknowledged(self):
        with self.lock:
            # print([x for x in self.acks])
            return len(self.unacknowledged) > 0


class SRSocket:
    def __init__(self):
        self.socket = None
        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.is_from_listener = None
        self.status = NOT_CONNECTED

        self.number_provider = AckNumberProvider()
        self.upstream_channel = MTByteStream()
        self.stop_flag = threading.Event()
        self.ack_register = AckRegister()
        self.socket_lock = threading.Lock()
        self.acker = BlockAcker(self.__send, self.upstream_channel)

    def from_listener(self, mux_demux_socket):
        logger.debug("Creating new SRSocket from listener")
        self.is_from_listener = True
        self.socket = mux_demux_socket
        self.packet_thread_handler.start()

    def stop(self):
        self.stop_flag.set()
        self.packet_thread_handler.join()
        self.socket.close()

    def connect(self, addr):
        self.is_from_listener = False
        logger.debug(f"Connecting to {addr[0]}:{addr[1]}")
        self.socket = MuxDemuxStream()
        self.socket.connect(addr)
        self.socket.settimeout(CONNACK_WAIT_TIMEOUT)
        for _ in range(CONNACK_RETRIES):
            try:
                logger.info("Sending CONNECT packet")
                self.socket.send_all(Connect().encode())
                logger.debug("Waiting for connack packet")
                packet = Packet.read_from_stream(self.socket)
                if packet.type == CONNACK:
                    logger.info("Received CONNACK packet")
                    self.status = CONNECTED
                    packet = Info(self.number_provider.get())
                    self.ack_register.add_pending(packet)
                    self.socket.send_all(packet.encode())
                    break
                else:
                    raise Exception(
                        "Received unexpected packet type from peer"
                    )
            except socket.timeout:
                logger.debug("Timed out waiting for CONNACK, sending again")

        if self.status != CONNECTED:
            raise Exception("Could not initialize connectiion")

        logger.debug("Connected")
        self.packet_thread_handler.start()

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
                self.handle_connect(packet)
            elif packet.type == CONNACK:
                self.handle_connack(packet)
            elif packet.type == INFO:
                self.handle_info(packet)
            elif packet.type == ACK:
                self.handle_ack(packet)
            else:
                logger.error("Received unknown packet type")

    def handle_info(self, packet):
        if self.status == NOT_CONNECTED:
            logger.error("Received INFO packet while not connected")
        elif self.status == CONNECTING:
            # Confirmo que ya se recibio el CONNACK
            self.status = CONNECTED

        self.acker.received(packet)

    def handle_connect(self, packet):
        if self.is_from_listener:
            if self.status == NOT_CONNECTED or self.status == CONNECTING:
                self.status = CONNECTING
                self.socket.send_all(Connack().encode())
            else:  # self.status == CONNECTED
                logger.debug(
                    "Received connect packet while already connected."
                )

        else:  # socket from client
            logger.error(
                "Received CONNECT packet when I was the one who"
                " initiated the connection"
            )

    def handle_connack(self, packet):
        logger.debug(
            "Received unexpected CONNACK packet, resending empty INFO package"
            " to confirm conection"
        )
        self.socket.send_all(Info(self.number_provider.get()).encode())

    def handle_ack(self, packet):
        if self.status != CONNECTED:
            logger.error("Receiving ACK packet while not connected")
        else:
            logger.debug("Receiving ACK packet")
            self.number_provider.push()
            self.ack_register.acknowledge(packet)

    def __check_ack(self, packet, send_attempt):
        if self.ack_register.pop_acknowledged(packet):
            return

        logger.warning(
            f"Packet with number {packet.number()} not acknowledged on time,"
            f" resending it (attempt {send_attempt})"
        )
        self.__send_packet(packet, send_attempt + 1)

    def __send(self, data):
        with self.socket_lock:
            self.socket.send_all(data)

    def __send_packet(self, packet, attempts=0):
        self.__send(packet.encode())
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
                self.__send_packet(packet)

    def recv(self, buff_size, timeout=None):
        logger.debug("Trying to receive data (buff_size %d)" % buff_size)
        info_body_bytes = self.upstream_channel.get_bytes(buff_size, timeout)
        logger.debug("Received data (%d bytes)" % len(info_body_bytes))
        return info_body_bytes
