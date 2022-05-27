import socket
import threading
import time
import logging
import random

from ..utils import MTByteStream

MAGIC_WORD = "ROSTOV"
PACKET_SIZE = 2**15

logger = logging.getLogger(__name__)

WINDOW_SIZE = 2**10

# Cuidado: esto no prueba la posibilidad de que un paquete se demore
# en la red, solo que se pierda
class BuggyUDPSocket:
    def __init__(self, buggyness_factor=0.0):
        self.buggyness_factor = buggyness_factor
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def sendto(self, data, addr):
        if random.random() > self.buggyness_factor:
            logger.debug("Dropping packet")
            return len(data)
        else:
            logger.debug("Sending packet")
            return self.socket.sendto(data, addr)

    def recvfrom(self, size):
        return self.socket.recvfrom(size)

    def close(self):
        return self.socket.close()

    def settimeout(self, timeout):
        return self.socket.settimeout(timeout)

    def setblocking(self, blocking):
        return self.socket.setblocking(blocking)

    def bind(self, addr):
        return self.socket.bind(addr)


def extract_packet(packet):
    magic_word = packet[: len(MAGIC_WORD)]
    magic_word = magic_word.decode("utf-8")
    if magic_word != MAGIC_WORD:
        logger.error(
            "Invalid magic word (expected %s, got %s)", MAGIC_WORD, magic_word
        )
    packet = packet[len(MAGIC_WORD) :]
    return packet


class MuxDemuxStream:
    def __init__(self):
        self.bytestream = None
        self.send_socket = None
        self.send_addr = None
        self.recv_socket = None
        # Only for stream created with connect()
        self.recv_thread_handle = None
        self.queue_timeout = None
        self.queue_block = True
        self.close_event = threading.Event()

    def connect(self, send_addr):
        self.send_addr = send_addr
        self.bytestream = MTByteStream()
        self.recv_socket = BuggyUDPSocket(buggyness_factor=0.2)
        self.send_socket = self.recv_socket
        self.recv_thread_handle = threading.Thread(target=self.recv_thread)
        self.recv_thread_handle.start()

    def from_listener(self, bytestream, send_socket, send_addr):
        logger.debug("Starting stream for listener")
        self.send_socket = send_socket
        self.send_addr = send_addr
        self.bytestream = bytestream

    def recv_thread(self):
        logger.debug("Starting receiver thread")
        self.recv_socket.settimeout(None)
        while True:
            try:
                data, addr = self.recv_socket.recvfrom(PACKET_SIZE)
                data = extract_packet(data)

                logger.debug("Received {} bytes from {} ({})".format(len(data), addr, data))

                if addr != self.send_addr:
                    raise Exception(
                        "Received packet from invalid address {} - Expected {}"
                        .format(addr, self.send_addr)
                    )
                self.bytestream.put_bytes(data)
            except socket.timeout:
                logger.debug("Timeout while receiving data")
                if self.close_event.is_set():
                    logger.debug("Receiver thread exiting")
                    return

    def send(self, buffer):
        logger.debug(
            "Sending {} bytes to {} ({})".format(
                len(buffer), self.send_addr, buffer
            )
        )
        self.send_socket.sendto(
            str.encode(MAGIC_WORD) + buffer, self.send_addr
        )
        # Siempre se envia la totalidad del paquete
        return len(buffer)

    def send_all(self, data):
        bytes_sent = 0
        while bytes_sent < len(data):
            bytes_sent += self.send(data[bytes_sent:])
        return bytes_sent

    def recv(self, buff_size):
        logger.debug("Receiving {} bytes, timeout: {} block: {}".format(buff_size, self.queue_timeout, self.queue_block))
        data = b""
        while len(data) < buff_size:
            new_data = self.bytestream.get_bytes(buff_size - len(data), self.queue_timeout, block=self.queue_block)
            if new_data != b"":
                data += new_data
            else:
                return data
        return data

    def recv_exact(self, buff_size):
        data = b""
        while True:
            data += self.recv(buff_size - len(data))
            if len(data) == buff_size:
                return data
            else:
                time.sleep(0.1)

    def settimeout(self, timeout):
        self.queue_timeout = timeout

    def setblocking(self, blocking):
        self.queue_block = blocking

    def close(self):
        logger.debug("Closing stream")
        self.close_event.set()
        if self.recv_thread_handle:
            self.recv_thread_handle.join()
            self.recv_socket.close()
