import socket
import threading
import time

from .buggy_udp import BuggyUDPSocket
from ..utils import MTByteStream

MAGIC_WORD = "ROSTOV"
PACKET_SIZE = 2**15


from loguru import logger

WINDOW_SIZE = 2**10


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
    def __init__(self, buggyness_factor=0.0):
        self.buggyness_factor = buggyness_factor

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
        self.recv_socket = BuggyUDPSocket(self.buggyness_factor)
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
        self.recv_socket.settimeout(1)
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
                if self.close_event.is_set():
                    logger.debug("Receiver thread exiting")
                    return

    def send(self, buffer):
        """
        logger.debug(
            "Sending {} bytes to {} ({})".format(
                len(buffer), self.send_addr, buffer
            )
        )
        """

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
        #logger.debug("Receiving {} bytes, timeout: {} block: {}".format(buff_size, self.queue_timeout, self.queue_block))
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
        # Socket generado con connect()
        if self.recv_thread_handle:
            self.recv_thread_handle.join()
            self.recv_socket.close()
        self.send_socket.close()

    def gettimeout(self):
        return self.queue_timeout

    def getblocking(self):
        return self.queue_block
