from .base import ClientStateBase
from .disconnected import ClientDisconnected
from .fin_sent import ClientFinSent
from .disconnecting import ClientDisconnecting


class ClientSendingFin(ClientStateBase):
    def set_disconnected(self):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def can_send(self):
        return False

    def can_recv(self):
        return True

    def handle_info(self, packet):
        self.saw_socket.send_ack_for(packet)

    def handle_ack(self, packet):
        pass

    def handle_fin(self, packet):
        self.saw_socket.send_finack_for(packet)
        self.saw_socket.set_state(ClientDisconnecting(self.saw_socket))

    def handle_finack(self, packet):
        self.saw_socket.received_finack(packet)
        self.saw_socket.set_state(ClientFinSent(self.saw_socket))

    def close(self):
        raise Exception("Socket closed more than once")
