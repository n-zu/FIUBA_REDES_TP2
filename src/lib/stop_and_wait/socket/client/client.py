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


class SAWSocketClient(SAWSocketInterface):
    CONNACK_WAIT_TIMEOUT = 5

    def __init__(self, initial_state):
        super().__init__(initial_state)

    def send_connect(self, addr):
        self.socket = MuxDemuxStream()
        self.socket.connect(addr)
        self.socket.settimeout(self.CONNACK_WAIT_TIMEOUT)
        self.socket.setblocking(True)

        while True:
            try:
                logger.debug("Sending connect packet")
                self.socket.send_all(bytes(ConnectPacket()))
                logger.debug("Waiting for connack packet")

                PacketFactory.read_connack(self.socket)
                break
            except socket.timeout:
                logger.debug("Time out waiting for CONNACK, sending again")
            except ProtocolViolation:
                logger.error("Protocol violation, closing connection")
                self.state.set_disconnected()
                self.stop()
                return
        logger.info("Received CONNACK, sending first INFO packet")
        while True:
            self.socket.send_all(
                bytes(
                    InfoPacket(
                        number=self.next_packet_number_to_send, body=b""
                    )
                )
            )
            try:
                PacketFactory.read_ack(self.socket)
                self.next_packet_number_to_send += 1
                self.state = ClientConnected(self)
                self.socket.settimeout(None)
                break
            except socket.timeout:
                logger.debug("Time out waiting for INFO, sending again")
            except ProtocolViolation:
                logger.error("Protocol violation, closing connection")
                self.socket.close()
                self.state = ClientDisconnected(self)
                return

        logger.debug("Connected")
        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.packet_thread_handler.start()
        self.info_bytestream = MTByteStream()

    def connect(self, addr):
        logger.info(f"Connecting to {addr[0]}:{addr[1]}")
        self.state.connect(addr)

    def handle_connect(self, packet):
        logger.error("Received connect packet from server")



