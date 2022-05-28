from abc import ABC
from loguru import logger
from ...states import SAWState


class ClientState(SAWState, ABC):
    def handle_connect(self, packet):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def set_disconnected(self):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    # Sobreescrito en ClientNotConnected
    def connect(self, addr):
        raise Exception("Already connected")


class ClientDisconnected(ClientState):
    def __init__(self, saw_socket):
        super().__init__(saw_socket)

    def can_send(self):
        return False

    def can_recv(self):
        return False

    def handle_connack(self, packet):
        pass

    def handle_info(self, packet):
        pass

    def handle_ack(self, packet):
        pass

    def handle_fin(self, packet):
        pass

    def handle_finack(self, packet):
        pass

    def close(self):
        raise Exception("Closed more than once")


class ClientFinRecv(ClientState):
    def can_send(self):
        return True

    def can_recv(self):
        return False

    def handle_connack(self, packet):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_info(self, packet):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_ack(self, packet):
        self.saw_socket.received_ack(packet)

    def handle_fin(self, packet):
        self.saw_socket.send_finack_for(packet)

    def handle_finack(self, packet):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def close(self):
        self.saw_socket.send_fin()
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))


class ClientFinSent(ClientState):
    def can_send(self):
        return False

    def can_recv(self):
        return True

    def handle_connack(self, packet):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

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

    def close(self):
        raise Exception("Socket closed more than once")


class ClientConnected(ClientState):
    def can_send(self):
        return True

    def can_recv(self):
        return True

    def handle_connack(self, packet):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_info(self, packet):
        self.saw_socket.send_ack_for(packet)

    def handle_ack(self, packet):
        self.saw_socket.received_ack(packet)

    def handle_fin(self, packet):
        self.saw_socket.send_finack_for(packet)
        self.saw_socket.set_state(ClientFinRecv(self.saw_socket))

    def handle_finack(self, packet):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def close(self):
        self.saw_socket.set_state(ClientFinSent(self.saw_socket))
        self.saw_socket.send_fin()


class ClientNotConnected(ClientState):
    def can_send(self):
        return True

    def can_recv(self):
        return False

    def handle_connack(self, packet):
        self.saw_socket.set_state(ClientConnected(self.saw_socket))

    def handle_info(self, packet):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_ack(self, packet):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_fin(self, packet):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_finack(self, packet):
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def close(self):
        self.saw_socket.stop()

    def connect(self, addr):
        self.saw_socket.send_connect(addr)
        self.saw_socket.set_state(ClientConnected(self.saw_socket))
