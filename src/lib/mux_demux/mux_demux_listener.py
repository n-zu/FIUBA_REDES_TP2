import queue
import threading
import time

from .mux_demux_stream import (
    socket,
    MuxDemuxStream,
    extract_packet,
    PACKET_SIZE,
)
from .buggy_udp import BuggyUDPSocket
from ..utils import MTByteStream

from loguru import logger


class SafeUDPSocket:
    def __init__(self, udp_socket):
        self.socket = udp_socket
        self.lock_send = threading.Lock()
        self.lock_recv = threading.Lock()

    def sendto(self, data, addr):
        with self.lock_send:
            bytes_sent = self.socket.sendto(data, addr)
        return bytes_sent

    def recvfrom(self, size):
        with self.lock_recv:
            data = self.socket.recvfrom(size)
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


# Wrapper para que MuxDemuxStream pueda hacer sendto()
# de manera thread safe
# Cuando se crea un Stream con from_listener(), se le pasa
# este objeto en vez del socket del listener
# Cuando el Stream manda un paquete, lo pone en la queue
# Despues el thread que ejecuta send_thread lo envia por el socket
class MTQueueWrapper:
    def __init__(self, addr):
        self.addr = addr
        self.queue = queue.SimpleQueue()

    def sendto(self, data, addr):
        self.queue.put((data, addr))
        return len(data)

    def get(self, block=True, timeout=None):
        return self.queue.get(block=block, timeout=timeout)


class MTSocketSender:
    def __init__(self, addr, my_queue):
        self.addr = addr
        self.queue = my_queue

    def sendto(self, data, addr):
        self.queue.put((data, addr))
        return len(data)

    def close(self):
        self.queue.put((None, self.addr))


class MuxDemuxListener:
    def __init__(self, buggyness_factor=0):
        self.buggyness_factor = buggyness_factor
        self.queue_timeout = None
        self.queue_block = True
        self.bind_addr = None
        self.queue_size = 0
        self.accept_addr = None
        self.accept_socket = None
        self.bytestreams = {}
        self.stop_event = threading.Event()
        self.waiting_connections = None
        self.queue_to_send = queue.SimpleQueue()

        self.recv_thread_handle = threading.Thread(target=self.recv_thread)
        self.send_thread_handle = threading.Thread(target=self.send_thread)

    def bind(self, bind_addr):
        logger.info("Binding listener to {}".format(bind_addr))
        self.bind_addr = bind_addr
        accept_socket = BuggyUDPSocket(self.buggyness_factor)
        accept_socket.bind(self.bind_addr)
        self.accept_socket = SafeUDPSocket(accept_socket)

    def listen(self, queue_size):
        logger.debug("Setting queue size to {}".format(queue_size))
        self.waiting_connections = queue.Queue(queue_size)
        self.recv_thread_handle.start()
        self.send_thread_handle.start()

    def accept(self):
        while True:
            try:
                addr = self.waiting_connections.get(
                    timeout=self.queue_timeout, block=self.queue_block
                )
                logger.debug("Accepted connection from {}".format(addr))
                socket_sender = MTSocketSender(addr, self.queue_to_send)

                new_stream = MuxDemuxStream()
                new_stream.from_listener(
                    self.bytestreams[addr], socket_sender, addr
                )
                return new_stream
            except queue.Empty:
                return None

    def send_thread(self):
        while True:
            try:
                (data, addr) = self.queue_to_send.get(timeout=1)
                # Me indica que el socket se desconecto
                if data is None:
                    del self.bytestreams[addr]
                    logger.debug(
                        f"Removing addr {addr} from bytestreams (now"
                        f" {len(self.bytestreams)} remaining)"
                    )
                else:
                    bytes_sent = 0
                    while bytes_sent < len(data):
                        bytes_sent += self.accept_socket.sendto(
                            data[bytes_sent:], addr
                        )
            except queue.Empty:
                if self.stop_event.is_set():
                    logger.debug("Stopping send thread")
                    break
                else:
                    continue

    def recv_thread(self):
        logger.debug("Starting accepter thread")
        self.accept_socket.settimeout(1)
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
            logger.trace("Received packet: {}".format(data))

            if addr not in self.bytestreams:
                if not self.waiting_connections.full():
                    # Necesito crear el bytestream aca porque el primer paquete
                    # puede contener informacion
                    logger.debug("Creating bytestream for {}".format(addr))
                    self.bytestreams[addr] = MTByteStream()
                    self.bytestreams[addr].put_bytes(data)
                    self.waiting_connections.put(addr)
                else:
                    # Queue is full
                    logger.warning("Queue is full")
            else:
                logger.debug("Adding packet to bytestream")
                self.bytestreams[addr].put_bytes(data)

    def close(self):
        while len(self.bytestreams) > 0:
            logger.warning(
                f"bytestreams is not empty: {self.bytestreams.keys()}"
            )
            time.sleep(2)
        self.stop_event.set()
        self.recv_thread_handle.join()
        self.send_thread_handle.join()
        self.accept_socket.close()

    def settimeout(self, timeout):
        self.queue_timeout = timeout

    def setblocking(self, blocking):
        self.queue_block = blocking
