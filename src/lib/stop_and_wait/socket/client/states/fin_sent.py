from .base import ClientStateBase
from .disconnected import ClientDisconnected


class ClientFinSent(ClientStateBase):
    def set_disconnected(self):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def can_send(self):
        return False

    def can_recv(self):
        return True

    def handle_info(self, packet):
        self.saw_socket.send_ack_for(packet)

    def handle_ack(self, packet):
        # Posiblemente pueda deberse a un paquete demorado en la red
        pass

    def handle_fin(self, packet):
        self.saw_socket.send_finack_for(packet)
        self.saw_socket.wait_for_fin_retransmission()
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_finack(self, packet):
        self.saw_socket.received_finack(packet)
