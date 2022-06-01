from loguru import logger
from .base import ServerStateBase
from .disconnected import ServerDisconnected
from .connected import ServerConnected
from .fin_recv import ServerFinRecv


class ServerConnecting(ServerStateBase):
    def set_disconnected(self):
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def can_send(self):
        return False

    def can_recv(self):
        return True

    def handle_connect(self, packet):
        self.saw_socket.send_connack_for(packet)

    def handle_info(self, packet):
        logger.success("Received first INFO packet, now fully connected")
        self.saw_socket.set_state(ServerConnected(self.saw_socket))
        self.saw_socket.send_ack_for(packet)
        self.saw_socket.connect_event.set()

    def handle_ack(self, packet):
        self.saw_socket.received_ack(packet)

    def handle_fin(self, packet):
        self.saw_socket.send_finack_for(packet)
        self.saw_socket.set_state(ServerFinRecv(self.saw_socket))

    def close(self):
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))
