import queue
import threading
import sys
import time

from .socket.client import SAWSocketClient
from .socket.server import SAWSocketServer

from lib.mux_demux.mux_demux_stream import MuxDemuxStream
from lib.utils import MTByteStream

from .packet import *

from loguru import logger


class SAWSocket:
    def __init__(self):
        self.socket = None
        self.timeout = None
        self.block = True

    def settimeout(self, timeout):
        if self.socket is None:
            self.timeout = timeout
        else:
            self.socket.settimeout(timeout)

    def setblocking(self, block):
        if self.socket is None:
            self.block = block
        else:
            self.socket.setblocking(block)

    def connect(self, addr):
        if self.socket is not None:
            raise Exception("Already connected")
        self.socket = SAWSocketClient()
        self.socket.connect(addr)
        self.socket.settimeout(self.timeout)
        self.socket.setblocking(self.block)

    def from_listener(self, mux_demux_socket):
        if self.socket is not None:
            raise Exception("Already connected")
        self.socket = SAWSocketServer()
        self.socket.from_listener(mux_demux_socket)
        self.socket.settimeout(self.timeout)
        self.socket.setblocking(self.block)

    def __getattr__(self, attr):
        if self.socket is None:
            raise Exception("Not connected")
        return getattr(self.socket, attr)
