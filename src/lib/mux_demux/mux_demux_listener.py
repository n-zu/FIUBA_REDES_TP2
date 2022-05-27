import queue
import threading
import logging
from .mux_demux_stream import (
    socket,
    MuxDemuxStream,
    extract_packet,
    PACKET_SIZE, BuggyUDPSocket,
)
from ..utils import MTByteStream

logger = logging.getLogger(__name__)


class SafeUDPSocket:
    def __init__(self, udp_socket):
        self.socket = udp_socket
        self.lock_send = threading.Lock()
        self.lock_recv = threading.Lock()

    def sendto(self, data, addr):
        #logger.debug("Acquiring lock for send")
        with self.lock_send:
            bytes_sent = self.socket.sendto(data, addr)
        #logger.debug("Releasing lock for send")
        return bytes_sent

    def recvfrom(self, size):
        #logger.debug("Acquiring lock for recv")
        with self.lock_recv:
            data = self.socket.recvfrom(size)
        #logger.debug("Releasing lock for recv")
        return data

    def close(self):
        with self.lock_send:
            value = self.socket.close()
        return value

    def settimeout(self, timeout):
        with self.lock_send:
            value = self.socket.settimeout(timeout)
        return value

    def setblocking(self, blocking):
        with self.lock_send:
            value = self.socket.setblocking(blocking)
        return value

    def bind(self, addr):
        with self.lock_send:
            value = self.socket.bind(addr)
        return value

# wrapper para que MuxDemuxStream pueda hacer sendto()
# de manera thread safe
class MTQueueWrapper:
    def __init__(self):
        self.queue = queue.SimpleQueue()

    def sendto(self, data, addr):
        self.queue.put((data, addr))
        return len(data)

    def get(self, block=True, timeout=None):
        return self.queue.get(block=block, timeout=timeout)


class MuxDemuxListener:
    def __init__(self):
        self.bind_addr = None
        self.queue_size = 0
        self.accept_addr = None
        self.accept_socket = None
        self.bytestreams = {}
        self.stop_event = threading.Event()
        self.waiting_connections = None
        self.queue_to_send = MTQueueWrapper()

        self.recv_thread_handle = threading.Thread(target=self.recv_thread)
        self.send_thread_handle = threading.Thread(target=self.send_thread)

    def bind(self, bind_addr):
        logger.info("Binding listener to {}".format(bind_addr))
        self.bind_addr = bind_addr
        accept_socket = BuggyUDPSocket()
        #accept_socket = socket.socket(
        #    family=socket.AF_INET, type=socket.SOCK_DGRAM
        #)
        accept_socket.bind(self.bind_addr)
        self.accept_socket = SafeUDPSocket(accept_socket)

    def listen(self, queue_size):
        logger.debug("Setting queue size to {}".format(queue_size))
        self.waiting_connections = queue.Queue(queue_size)
        self.recv_thread_handle.start()
        self.send_thread_handle.start()

    def accept(self):
        logger.info("Accepting connection")
        while True:
            try:
                addr = self.waiting_connections.get()
                logger.debug("Accepted connection from {}".format(addr))
                new_stream = MuxDemuxStream()
                new_stream.from_listener(
                    self.bytestreams[addr], self.queue_to_send, addr
                )
                return new_stream
            except queue.Empty:
                if self.stop_event.is_set():
                    logger.debug("Stopping accept thread")
                    break

    def send_thread(self):
        while True:
            try:
                (packet_to_send, addr) = self.queue_to_send.get()
                bytes_sent = 0
                while bytes_sent < len(packet_to_send):
                    bytes_sent += self.accept_socket.sendto(
                        packet_to_send[bytes_sent:], addr
                    )
            except queue.Empty:
                if self.stop_event.is_set():
                    logger.debug("Stopping send thread")
                    break

    def recv_thread(self):
        logger.debug("Starting accepter thread")
        while True:
            try:
                data, addr = self.accept_socket.recvfrom(PACKET_SIZE)
            except socket.timeout:
                if self.stop_event.is_set():
                    logger.debug("Stopping recv thread")
                    break
                else:
                    continue

            data = extract_packet(data)
            logger.debug("Received packet: {}".format(data))

            if not self.waiting_connections.full():
                if addr not in self.bytestreams:
                    # Necesito crear el bytestream aca porque el primer paquete
                    # puede contener informacion
                    self.bytestreams[addr] = MTByteStream()
                    self.bytestreams[addr].put_bytes(data)
                    self.waiting_connections.put(addr)
                else:
                    self.bytestreams[addr].put_bytes(data)
            else:
                # Queue is full
                logger.warning("Queue is full")

    def close(self):
        self.stop_event.set()
        self.recv_thread_handle.join()
        self.send_thread_handle.join()
        self.accept_socket.close()
