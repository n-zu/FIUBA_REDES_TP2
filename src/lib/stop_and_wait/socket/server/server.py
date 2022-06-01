from lib.utils import MTByteStream
from ..interface import *


class SAWSocketServer(SAWSocketInterface):
    def __init__(self, initial_state):
        super().__init__(initial_state)
        self.connect_event = threading.Event()

    def from_listener(self, mux_demux_socket):
        self.socket = mux_demux_socket

        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.info_bytestream = MTByteStream()
        self.packet_thread_handler.start()
        # Wait for CONNECT
        self.connect_event.wait()

    def handle_connect(self, packet):
        logger.debug(f"Received CONNECT packet while in state {self.state}")
        self.state.handle_connect(packet)

    def send_connack_for(self, _packet):
        logger.debug("Sending CONNACK for CONNECT packet")
        self.socket.send_all(bytes(ConnackPacket()))

