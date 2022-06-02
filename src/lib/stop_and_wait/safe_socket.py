import threading
from .packet import PacketFactory


class SafeSocket:
    def __init__(self, a_socket):
        self.socket = a_socket
        # Si falla cambiar por RLock
        self.send_lock = threading.Lock()
        self.recv_lock = threading.Lock()

    def send_all(self, data):
        with self.send_lock:
            self.socket.send_all(data)

    def recv(self, size):
        with self.recv_lock:
            return self.socket.recv(size)

    def read_packet(self):
        with self.recv_lock:
            packet = PacketFactory.read_from_stream(self.socket)
        return packet

    def close(self):
        with self.recv_lock:
            self.socket.close()

    def __getattr__(self, name):
        return getattr(self.socket, name)
