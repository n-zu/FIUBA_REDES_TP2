from .base import ClientStateBase
from .disconnected import ClientDisconnected
from .connecting import ClientConnecting


class ClientNotConnected(ClientStateBase):
    def set_disconnected(self):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def can_send(self):
        return True

    def can_recv(self):
        return False

    def close(self):
        self.saw_socket.stop()

    def connect(self, addr):
        self.saw_socket.set_state(ClientConnecting(self.saw_socket))
        self.saw_socket.safe_connect(addr)
