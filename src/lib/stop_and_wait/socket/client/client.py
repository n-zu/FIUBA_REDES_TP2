import threading

from .states import *
from ....mux_demux.mux_demux_stream import MuxDemuxStream

from ..interface import SAWSocketInterface
from ...exceptions import ProtocolViolation
from ...packet import *


# No envie el CONNECT (si soy socket) ni lo recibi (si soy listener)
from ....utils import MTByteStream

NOT_CONNECTED = "NOT_CONNECTED"
# Soy Socket de listener, mande el CONNACK y ya recibi info
# (confirma que el cliente recibio el CONNECT)
CONNECTING = "CONNECTING"
# Soy Socket de listener, y recibi el CONNECT
CONNECTED = "CONNECTED"
# Mande FIN, pero no recibi FINACK
DISCONNECTING = "DISCONNECTING"
# Mande FIN y recibi FINACK
DISCONNECTED = "DISCONNECTED"


class SafeSocket:
    def __init__(self, a_socket):
        self.socket = a_socket
        self.lock_send = threading.Lock()
        self.lock_recv = threading.Lock()

    def connect(self, addr):
        with self.lock_send:
            value = self.socket.connect(addr)
        return value

    def send(self, buffer):
        with self.lock_send:
            bytes_sent = self.socket.send(buffer)
        return bytes_sent

    def recv(self, size):
        with self.lock_recv:
            data = self.socket.recv(size)
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

    def send_all(self, buffer):
        with self.lock_send:
            value = self.socket.sendall(buffer)
        return value


class SAWSocketClient(SAWSocketInterface):
    CONNACK_WAIT_TIMEOUT = 2

    def __init__(self, initial_state, buggyness_factor=0):
        super().__init__(initial_state)
        self.buggyness_factor = buggyness_factor

    def send_connect(self, addr):
        self.socket = MuxDemuxStream(self.buggyness_factor)
        self.socket.connect(addr)
        self.socket.settimeout(self.CONNACK_WAIT_TIMEOUT)
        self.socket.setblocking(True)

        while True:
            try:
                logger.debug("Sending connect packet")
                self.socket.send_all(bytes(ConnectPacket()))

                PacketFactory.read_connack(self.socket)
                break
            except socket.timeout:
                logger.debug("Timeout waiting for CONNACK, sending again")
            except ProtocolViolation:
                raise ProtocolViolation("Received packet distinct from CONNACK while in CONNECTING state")
                logger.error("Protocol violation, closing connection")
                self.state.set_disconnected()
                self.stop()
                return
        self.set_state(ClientConnected(self))
        self.info_bytestream = MTByteStream()
        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.packet_thread_handler.start()
        self.send(b"")
        logger.success("Connected")

    def connect(self, addr):
        logger.info(f"Connecting to {addr[0]}:{addr[1]}")
        self.state.connect(addr)

    def handle_connect(self, packet):
        raise Exception("Received CONNECT packet while in state {}".format(self.state))
        logger.error("Received connect packet from server")



