from .base import ServerStateBase
from .connecting import ServerConnecting
from .disconnected import ServerDisconnected


class ServerNotConnected(ServerStateBase):
    def set_disconnected(self):
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def can_send(self):
        return False

    def can_recv(self):
        return True

    def handle_connect(self, packet):
        self.saw_socket.send_connack_for(packet)
        self.saw_socket.set_state(ServerConnecting(self.saw_socket))

    def close(self):
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

