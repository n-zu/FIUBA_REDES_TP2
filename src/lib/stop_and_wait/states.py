from abc import ABC, abstractmethod
from loguru import logger


class SAWState(ABC):
    def __init__(self, saw_socket):
        self.saw_socket = saw_socket

    @abstractmethod
    def handle_connect(self, packet):
        pass

    @abstractmethod
    def handle_connack(self, packet):
        pass

    @abstractmethod
    def handle_info(self, packet):
        pass

    @abstractmethod
    def handle_ack(self, packet):
        pass

    @abstractmethod
    def handle_fin(self, packet):
        pass

    @abstractmethod
    def handle_finack(self, packet):
        pass


class ConnectedState(SAWState):



class DisconnectedState(SAWState):
    pass


class ConnectingState(SAWState):
    pass


class NotConnectedState(SAWState):
    def handle_connect(self, packet):
        self.saw_socket.state = ConnectingState(self.saw_socket)
        self.saw_socket.send_connack()

    def handle_connack(self, packet):
        self.saw_socket.state = DisconnectedState(self.saw_socket)

    def handle_info(self, packet):
        self.saw_socket.state = DisconnectedState(self.saw_socket)

    def handle_ack(self, packet):
        self.saw_socket.state = DisconnectedState(self.saw_socket)

    def handle_fin(self, packet):
        self.saw_socket.state = DisconnectedState(self.saw_socket)
        
    def handle_finack(self, packet):
        self.saw_socket.state = DisconnectedState(self.saw_socket)