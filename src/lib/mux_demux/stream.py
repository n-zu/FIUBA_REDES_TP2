import socket
import threading
import time
import logging

from lib.utils import MTByteStream

MAGIC_WORD = "ROSTOV"
PACKET_SIZE = 2**15

logger = logging.getLogger(__name__)

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
    def __init__(self):
        self.bytestream = None
        self.send_socket = None
        self.send_addr = None
        self.recv_socket = None
        self.recv_thread_handle = None
        self.queue_timeout = None

    def connect(self, send_addr):
        self.send_addr = send_addr
        self.bytestream = MTByteStream()
        self.recv_socket = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_DGRAM
        )
        self.send_socket = self.recv_socket
        self.recv_thread_handle = threading.Thread(target=self.receiver_thread)
        self.recv_thread_handle.start()

    def from_listener(self, bytestream, send_socket, send_addr):
        logger.debug(
            "Starting stream for listener with {}".format(send_socket)
        )
        self.send_socket = send_socket
        self.send_addr = send_addr
        self.bytestream = bytestream

    def receiver_thread(self):
        logger.debug("Starting receiver thread")
        while True:
            try:
                data, addr = self.recv_socket.recvfrom(PACKET_SIZE)
                logger.debug(
                    "Received {} bytes from {}".format(len(data), addr)
                )
                data = extract_packet(data)
                if addr != self.send_addr:
                    raise Exception(
                        "Received packet from invalid address {} - Expected {}"
                        .format(addr, self.send_addr)
                    )
                self.bytestream.put_bytes(data)
            except socket.timeout:
                pass
                # check flag for stopping thread

    def send(self, buffer):
        logger.debug(
            "Sending {} bytes to {} ({})".format(
                len(buffer), self.send_addr, buffer
            )
        )
        bytes_sent = self.send_socket.sendto(
            str.encode(MAGIC_WORD) + buffer, self.send_addr
        )
        return bytes_sent

    def send_all(self, data):
        bytes_sent = 0
        while bytes_sent < len(data):
            bytes_sent += self.send(data[bytes_sent:])
        return bytes_sent

    def recv(self, buff_size):
        data = self.bytestream.get_bytes(buff_size, self.queue_timeout)
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
