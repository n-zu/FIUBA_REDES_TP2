from lib.mux_demux.stream import MuxDemuxStream
import logging
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

logger = logging.getLogger(__name__)

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
        return self.channel.get()

    def push(self):
        self.channel.put(self.next)
        self.next += 1
        self.next %= ACK_NUMBERS


# Hace ACK a los INFO recibidos y los envia por la queue
class BlockAcker:
    def __init__(self, socket, queue):
        self.last_received = None
        self.blocks = {}
        self.socket = socket
        self.queue = queue

    def __send_stored(self):
        i = self.last_received
        while i in self.blocks:
            self.queue.put_bytes(self.blocks[i].body())
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
        else:
            self.blocks[packet.number()] = packet

        self.socket.send_all(Ack(packet.number()).encode())


class Acker:
    def __init__(self):
        self.lock = threading.Lock()
        self.acks = set()

    def acknowledge(self, packet):
        with self.lock:
            self.acks.add(packet.number())

    def pop_acknowledged(self, packet):
        with self.lock:
            if packet.number() in self.acks:
                self.acks.remove(packet.number())
                return True
            return False


class SRSocket:
    def __init__(self):
        self.socket = None
        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.is_from_listener = None
        self.status = NOT_CONNECTED

        self.number_provider = AckNumberProvider()
        self.info_bytestream = MTByteStream()
        self.stop_flag = threading.Event()
        self.acker = Acker()
        self.socket_lock = threading.Lock()

    def from_listener(self, mux_demux_socket):
        logger.debug("Creating new SRSocket from listener")
        self.is_from_listener = True
        self.socket = mux_demux_socket
        self.acker = BlockAcker(self.socket, self.info_bytestream)
        self.packet_thread_handler.start()

    def stop(self):
        self.stop_flag.set()
        self.packet_thread_handler.join()

    def connect(self, addr):
        self.is_from_listener = False
        logger.debug(f"Connecting to {addr[0]}:{addr[1]}")
        self.socket = MuxDemuxStream()
        self.acker = BlockAcker(self.socket, self.info_bytestream)
        self.socket.connect(addr)
        self.socket.settimeout(CONNACK_WAIT_TIMEOUT)
        for _ in range(CONNACK_RETRIES):
            try:
                logger.debug("Sending connect packet")
                self.socket.send_all(Connect().encode())
                logger.debug("Waiting for connack packet")
                packet = Packet.read_from_stream(self.socket)
                if packet.type == CONNACK:
                    self.status = CONNECTED
                    self.socket.send_all(
                        Info(self.number_provider.get()).encode()
                    )
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

        while not self.stop_flag.is_set():
            try:
                packet = Packet.read_from_stream(self.socket)
            except TimeoutError:
                continue
            logger.debug(f"Received packet of type {packet.type}")
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
            self.acked.put(packet.number())

    def __check_ack(self, packet):
        if self.acked.pop_acknoledged(packet):
            return
        self.__send_packet(packet)

    def __send_packet(self, packet):
        packet.set_number(self.number_provider.get())
        logger.debug("Sending packet %d" % packet.number())
        with self.socket_lock:
            self.socket.send_all(packet.encode())
        threading.Timer(ACK_TIMEOUT, self.__check_ack, [packet])

    def send(self, buffer):
        logger.debug(f"Sending buffer {buffer}")

        if self.status != CONNECTED:
            logger.error("Trying to send data while not connected")
        else:
            logger.debug("Sending data")
            packets = Info.from_buffer(buffer, MAX_SIZE)
            logger.debug("Fragmented buffer into %d packets" % len(packets))

            for packet in packets:
                self.__send_packet(packet)

    def recv(self, buff_size, timeout=None):
        logger.debug("Receiving data (buff_size %d)" % buff_size)
        info_body_bytes = self.info_bytestream.get_bytes(buff_size, timeout)
        logger.debug("Received INFO packet (%d bytes)" % len(info_body_bytes))
        return info_body_bytes
