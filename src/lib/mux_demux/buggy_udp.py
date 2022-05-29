# Cuidado: esto no prueba la posibilidad de que un paquete se demore
# en la red, solo que se pierda
import random
import socket

from loguru import logger


class BuggyUDPSocket:
    def __init__(self, buggyness_factor=0.0):
        self.buggyness_factor = buggyness_factor
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def sendto(self, data, addr):
        if random.random() > self.buggyness_factor:
            return self.socket.sendto(data, addr)
        else:
            logger.warning(f"Lost packet {data}")
        return len(data)

    def recvfrom(self, size):
        return self.socket.recvfrom(size)

    def close(self):
        return self.socket.close()

    def settimeout(self, timeout):
        return self.socket.settimeout(timeout)

    def setblocking(self, blocking):
        return self.socket.setblocking(blocking)

    def bind(self, addr):
        return self.socket.bind(addr)

