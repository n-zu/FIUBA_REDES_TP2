from .base import ServerStateBase


class ServerDisconnected(ServerStateBase):
    def set_disconnected(self):
        pass

    def can_send(self):
        return False

    def can_recv(self):
        return False

