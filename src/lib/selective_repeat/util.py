from .constants import (
    INITIAL_PACKET_NUMBER,
    NOT_CONNECTED,
    WINDOW_SIZE,
    ACK_NUMBERS,
)
from loguru import logger
import threading
import queue


# Maneja la window actual y bloquea el get() hasta que haya
# espacio en la window
class AckNumberProvider:
    def __init__(self, window_size=WINDOW_SIZE):
        self.oldest_not_acked = INITIAL_PACKET_NUMBER
        self.acked = set()
        self.lock = threading.Lock()
        self.available = queue.SimpleQueue()
        for i in range(
            INITIAL_PACKET_NUMBER, INITIAL_PACKET_NUMBER + window_size
        ):
            self.available.put(i)

    def get(self, timeout=None):
        n = self.available.get(timeout=timeout)
        return n

    def push(self, number):
        with self.lock:
            if self.oldest_not_acked == number:
                self.acked.add(number)
                self.__update_oldest()
            elif gt_packets(number, self.oldest_not_acked):
                self.acked.add(number)

    def __update_oldest(self):
        while self.oldest_not_acked in self.acked:
            self.available.put(
                (self.oldest_not_acked + WINDOW_SIZE) % ACK_NUMBERS
            )
            self.acked.remove(self.oldest_not_acked)
            self.oldest_not_acked = (self.oldest_not_acked + 1) % ACK_NUMBERS


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

        logger.debug(
            f"Added pending acknowledgement for packet {packet.number()}"
        )

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
        with self.lock:
            self.status = status

    def get(self):
        with self.lock:
            return self.status
