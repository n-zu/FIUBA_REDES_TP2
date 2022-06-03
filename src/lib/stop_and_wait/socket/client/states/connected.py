from .base import ClientStateBase
from .fin_recv import ClientFinRecv
from .sending_fin import ClientSendingFin
from .disconnected import ClientDisconnected


class ClientConnected(ClientStateBase):
    def set_disconnected(self):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def can_send(self):
        return True

    def can_recv(self):
        return True

    def handle_connack(self, packet):
        pass

    def handle_info(self, packet):
        self.saw_socket.send_ack_for(packet)

    def handle_ack(self, packet):
        self.saw_socket.received_ack(packet)

    def handle_fin(self, packet):
        self.saw_socket.set_state(ClientFinRecv(self.saw_socket))
        self.saw_socket.send_finack_for(packet)

    """
    Descomentar esta linea si falla
    def handle_finack(self, packet):
        #raise Exception("Received FINACK while in state ClientConnected")
        self.saw_socket.received_finack(packet)
    """

    def close(self):
        self.saw_socket.set_state(ClientSendingFin(self.saw_socket))
        self.saw_socket.send_fin_reliably()
