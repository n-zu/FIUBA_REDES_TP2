from .base import ClientStateBase
from .disconnected import ClientDisconnected


class ClientFinRecv(ClientStateBase):
    def set_disconnected(self):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def can_send(self):
        return True

    def can_recv(self):
        return False

    def handle_ack(self, packet):
        self.saw_socket.received_ack(packet)

    def handle_fin(self, packet):
        self.saw_socket.send_finack_for(packet)

    def handle_finack(self, packet):
        self.saw_socket.received_finack(packet)

    def close(self):
        self.saw_socket.send_fin_reliably()
        self.saw_socket.wait_for_fin_retransmission()
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))