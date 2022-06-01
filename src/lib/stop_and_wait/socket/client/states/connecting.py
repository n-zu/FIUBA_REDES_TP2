import threading
from loguru import logger
from .base import ClientStateBase
from .connected import ClientConnected
from .disconnected import ClientDisconnected


class ClientConnecting(ClientStateBase):
    def set_disconnected(self):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def can_send(self):
        return False

    def can_recv(self):
        return False

    def handle_connack(self, packet):
        logger.success("Received CONNACK, now fully connected")
        self.saw_socket.set_state(ClientConnected(self.saw_socket))
        self.saw_socket.packet_thread_handler = threading.Thread(
            target=self.saw_socket.packet_handler
        )
        self.saw_socket.packet_thread_handler.start()
        self.saw_socket.send(b"")
