from .base import ServerStateBase
from .disconnected import ServerDisconnected
from .fin_recv import ServerFinRecv
from .sending_fin import ServerSendingFin


class ServerConnected(ServerStateBase):
    def set_disconnected(self):
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def can_send(self):
        return True

    def can_recv(self):
        return True

    def handle_info(self, packet):
        self.saw_socket.send_ack_for(packet)

    def handle_ack(self, packet):
        self.saw_socket.received_ack(packet)

    def handle_fin(self, packet):
        self.saw_socket.set_state(ServerFinRecv(self.saw_socket))
        self.saw_socket.send_finack_for(packet)

    def handle_finack(self, packet):
        self.saw_socket.received_finack(packet)

    def close(self):
        self.saw_socket.set_state(ServerSendingFin(self.saw_socket))
        self.saw_socket.send_fin_reliably()
