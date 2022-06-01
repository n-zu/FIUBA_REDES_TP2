import threading
from abc import ABC, abstractmethod
from loguru import logger


class SAWState(ABC):
    def __init__(self, saw_socket):
        self.saw_socket = saw_socket

    def __repr__(self):
        return self.__class__.__name__

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

    @abstractmethod
    def can_send(self):
        pass

    @abstractmethod
    def can_recv(self):
        pass

    @abstractmethod
    def set_disconnected(self):
        pass

    @abstractmethod
    def close(self):
        pass