import threading
from loguru import logger

from .interface import *
from ...utils import MTByteStream


class SAWSocketServer(SAWSocketInterface):
    def __init__(self):
        super().__init__()
        self.connect_event = threading.Event()

    def from_listener(self, mux_demux_socket):
        self.socket = mux_demux_socket

        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.packet_thread_handler.start()
        self.info_bytestream = MTByteStream()
        # Wait for CONNECT
        self.connect_event.wait()

    def handle_connect(self, packet):
        logger.debug("Received CONNECT packet")

        if self.status.is_equal(NOT_CONNECTED) or self.status.is_equal(
            CONNECTING
        ):
            self.status.set(CONNECTING)
            self.connect_event.set()
            logger.debug("Sending CONNACK")
            self.socket.send_all(bytes(ConnackPacket()))
        else:  # self.status == CONNECTED
            logger.error("Received connect packet while already connected")
