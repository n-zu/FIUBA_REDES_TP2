import threading
import logging
from .stream import (
    socket,
    MTByteStream,
    MuxDemuxStream,
    extract_packet,
    PACKET_SIZE,
    time,
)

logger = logging.getLogger(__name__)


class MuxDemuxListener:
    def __init__(self):
        self.bind_addr = None
        self.queue_size = 0
        self.waiting_connections = None
        self.accept_addr = None
        self.bytestreams = None
        self.accept_socket = None
        self.accept_thread_handle = threading.Thread(target=self.accept_thread)

    def bind(self, bind_addr):
        logger.info("Binding listener")
        self.bind_addr = bind_addr
        self.queue_size = 0
        self.waiting_connections = []
        self.bytestreams = {}

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
                    self.bytestreams[addr], self.accept_socket, addr
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
