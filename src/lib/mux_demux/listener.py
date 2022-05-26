import queue
import threading
import logging
from .stream import (
    socket,
    MuxDemuxStream,
    extract_packet,
    PACKET_SIZE,
    time,
)
from ..utils import MTByteStream

logger = logging.getLogger(__name__)


class MTQueueWrapper:
    def __init__(self, queue):
        self.queue = queue

    def sendto(self, data, addr):
        self.queue.put((data, addr))
        return len(data)

    def get(self, block=True, timeout=None):
        return self.queue.get(block=block, timeout=timeout)


class MuxDemuxListener:
    def __init__(self):
        self.bind_addr = None
        self.queue_size = 0
        self.waiting_connections = None
        self.accept_addr = None
        self.bytestreams = None
        self.accept_socket = None
        self.queue_to_send = MTQueueWrapper(queue.Queue())

        self.accept_thread_handle = threading.Thread(target=self.accept_thread)
        self.send_thread_handle = threading.Thread(target=self.send_thread)

    def bind(self, bind_addr):
        logger.info("Binding listener")
        self.bind_addr = bind_addr
        self.queue_size = 0
        self.waiting_connections = []
        self.bytestreams = {}

    def send_thread(self):
        while True:
            (packet_to_send, addr) = self.queue_to_send.get()
            bytes_sent = 0
            while bytes_sent < len(packet_to_send):
                bytes_sent += self.accept_socket.sendto(
                    packet_to_send[bytes_sent :], addr
                )

    def accept_thread(self):
        logger.debug("Starting accepter thread")
        while True:
            data, addr = self.accept_socket.recvfrom(PACKET_SIZE)
            logger.debug(
                "Received {} bytes from {} ({})".format(
                    len(data), addr, data.decode("utf-8")
                )
            )

            data = extract_packet(data)
            logger.debug("Extracted packet: {}".format(data))

            if len(self.waiting_connections) < self.queue_size:
                if addr not in self.bytestreams:
                    print("Adding bytestream for {}".format(addr))
                    # Necesito crear el bytestream aca porque el primer paquete
                    # puede contener informacion
                    self.bytestreams[addr] = MTByteStream()
                    self.bytestreams[addr].put_bytes(data)
                    self.waiting_connections.append(addr)
                else:
                    logger.debug("Putting bytes {}".format(data))
                    self.bytestreams[addr].put_bytes(data)
            else:
                # Queue is full
                logger.warning("Queue is full")

    def accept(self):
        logger.info("Accepting connection")
        while True:
            if len(self.waiting_connections) > 0:
                addr = self.waiting_connections.pop(0)
                logger.info("Accepted connection from {}".format(addr))
                new_stream = MuxDemuxStream()

                new_stream.from_listener(
                    self.bytestreams[addr], self.queue_to_send, addr
                )
                return new_stream
            else:
                time.sleep(0.5)
                continue

    def listen(self, queue_size):
        logger.debug("Setting queue size to {}".format(queue_size))
        self.queue_size = queue_size
        accept_socket = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_DGRAM
        )
        accept_socket.bind(self.bind_addr)
        self.accept_socket = accept_socket
        self.accept_thread_handle.start()
        self.send_thread_handle.start()
