from .socket.client.client import SAWSocketClient
from .socket.server.server import SAWSocketServer
from .socket.client.states.not_connected import ClientNotConnected
from .socket.server.states.not_connected import ServerNotConnected


class SAWSocket:
    def __init__(self, buggyness_factor=0.0):
        self.socket = None
        self.timeout = None
        self.block = True
        self.buggyness_factor = buggyness_factor

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
        self.socket = SAWSocketClient(ClientNotConnected(self), buggyness_factor=self.buggyness_factor)
        self.socket.connect(addr)
        self.socket.settimeout(self.timeout)
        self.socket.setblocking(self.block)

    def from_listener(self, mux_demux_socket):
        if self.socket is not None:
            raise Exception("Already connected")
        self.socket = SAWSocketServer(ServerNotConnected(self))
        self.socket.from_listener(mux_demux_socket)
        self.socket.settimeout(self.timeout)
        self.socket.setblocking(self.block)

    def __getattr__(self, attr):
        if self.socket is None:
            raise Exception(f"Not connected while trying to access {attr}")
        return getattr(self.socket, attr)
