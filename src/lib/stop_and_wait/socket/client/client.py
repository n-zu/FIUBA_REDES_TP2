import socket
from loguru import logger
import threading
from ....mux_demux.mux_demux_stream import MuxDemuxStream
from ..interface import SAWSocketInterface
from ...exceptions import ProtocolError
from ...packet import PacketFactory, ConnectPacket
from ....utils import MTByteStream


class SAWSocketClient(SAWSocketInterface):
    CONNACK_WAIT_TIMEOUT = 2

    def __init__(self, initial_state, buggyness_factor=0):
        super().__init__(initial_state)
        self.buggyness_factor = buggyness_factor

    def safe_connect(self, addr):
        self.socket = MuxDemuxStream(self.buggyness_factor)
        self.socket.connect(addr)
        self.socket.settimeout(self.CONNACK_WAIT_TIMEOUT)
        self.socket.setblocking(True)

        while True:
            try:
                logger.trace("Sending connect packet")
                self.socket.send_all(bytes(ConnectPacket()))

                connack = PacketFactory.read_connack(self.socket)
                break
            except socket.timeout:
                logger.trace("Timeout waiting for CONNACK, sending again")
            except ProtocolError as e:
                logger.error(f"Protocol error: {e}")
                self.stop()
                return
        self.info_bytestream = MTByteStream()
        self.state.handle_connack(connack)
        logger.success("Connected")

    def connect(self, addr):
        logger.info(f"Connecting to {addr[0]}:{addr[1]}")
        self.state.connect(addr)

    def handle_connect(self, packet):
        self.state.handle_connect(packet)

