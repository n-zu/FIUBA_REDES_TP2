from .constants import (
    INITIAL_PACKET_NUMBER,
    NOT_CONNECTED,
    WINDOW_SIZE,
    ACK_NUMBERS,
)
import queue
from loguru import logger
import threading


# Cuenta los paquetes on-flight y bloquea el get() hasta que haya
# espacio en la window
class AckNumberProvider:
    def __init__(self, timeout=None, window_size=WINDOW_SIZE):
        self.next = INITIAL_PACKET_NUMBER + WINDOW_SIZE
        self.channel = queue.SimpleQueue()
        for i in range(
            INITIAL_PACKET_NUMBER, INITIAL_PACKET_NUMBER + WINDOW_SIZE
        ):
            self.channel.put(i % ACK_NUMBERS)
        self.timeout = timeout

    def get(self):
        n = self.channel.get(timeout=self.timeout)
        return n

    def push(self):
        self.channel.put(self.next)
        self.next += 1
        self.next %= ACK_NUMBERS


# Función de comparación de paquetes (greater than)
def gt_packets(packet_number, other_packet_number):
    # Si entra al if, esta wrappeando los acks (ej.: 10 > 4294967295,
    # porque me tiene que llegar el ack del 4294967295 antes que el del 10)
    if packet_number + ACK_NUMBERS - other_packet_number <= ACK_NUMBERS / 2:
        return True

    return packet_number > other_packet_number


# Hace ACK a los INFO recibidos y los envia al upstream en orden
class BlockAcker:
    def __init__(self, sender, upstream_channel):
        self.last_received = INITIAL_PACKET_NUMBER - 1
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
        if (self.last_received + 1) % ACK_NUMBERS == packet.number():
            self.last_received = packet.number()
            self.blocks[packet.number()] = packet
            self.__send_stored()
        elif gt_packets(packet.number(), self.last_received):
            self.blocks[packet.number()] = packet

        ack = packet.ack()
        logger.info(f"Sending {ack}")
        self.sender(ack.encode())


# Registra que paquetes tienen ack pendiente
class AckRegister:
    def __init__(self):
        self.lock = threading.Lock()
        self.unacknowledged = set()
        self.first_acked = None
        self.stopped = threading.Event()

    def add_pending(self, packet):
        if self.stopped.is_set():
            logger.warning(
                f"Tried to set packet {packet.number()} as pending, but"
                " the AckRegister is stopped"
            )
            return
        with self.lock:
            self.unacknowledged.add(packet.number())

    def acknowledge(self, packet):
        self.__set_first(packet.number())
        with self.lock:
            self.unacknowledged.discard(packet.number())

    # Devuelve true si fue recibió Ack, false sino
    def check_acknowledged(self, packet):
        with self.lock:
            return not packet.number() in self.unacknowledged

    def have_unacknowledged(self):
        with self.lock:
            return len(self.unacknowledged) > 0

    # Ignorar los futuros add_pending() y marcar todos como ACKed
    def stop(self):
        self.stopped.set()
        with self.lock:
            if len(self.unacknowledged) > 0:
                logger.warning(
                    "Clearing unacknowledged packets on AckRegister, but ACKs"
                    " not received for numbers "
                    + str(self.unacknowledged)
                )
            self.unacknowledged.clear()

    def __set_first(self, number):
        if self.first_acked and number == INITIAL_PACKET_NUMBER:
            self.first_acked.set()
            logger.debug("First INFO packet acked")

    def enable_wait_first(self):
        self.first_acked = threading.Event()

    def wait_first_acked(self, timeout=None):
        if self.first_acked:
            self.first_acked.wait(timeout=timeout)


class SafeSendSocket:
    def __init__(self, socket=None):
        self.socket = socket
        self.send_lock = threading.Lock()

    def set_socket(self, socket):
        self.socket = socket

    def send_all(self, data):
        if self.socket is None:
            raise Exception("No socket has been set")
        with self.send_lock:
            self.socket.send_all(data)


class SocketStatus:
    def __init__(self, status=NOT_CONNECTED):
        self.status = status
        self.lock = threading.Lock()

    def set_status(self, status):
        self.status = status

    def get(self):
        with self.lock:
            return self.status
