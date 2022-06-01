from abc import ABC
from loguru import logger
from ...states import SAWState


class ClientState(SAWState, ABC):
    def handle_connect(self, packet):
        logger.debug(f"Received CONNECT packet while in state {self.saw_socket.state}")
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def set_disconnected(self):
        logger.debug("Setting state to ClientDisconnected")
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
        raise Exception("Received CONNACK while disconnected")

    def handle_info(self, packet):
        raise Exception("Received INFO while disconnected")

    def handle_ack(self, packet):
        raise Exception("Received ACK while disconnected")

    def handle_fin(self, packet):
        raise Exception("Received FIN while disconnected")

    def handle_finack(self, packet):
        pass
        #raise Exception("Received FINACK while disconnected")

    def close(self):
        raise Exception("Closed more than once")


class ClientFinRecv(ClientState):
    def can_send(self):
        return True

    def can_recv(self):
        return False

    def handle_connack(self, packet):
        raise Exception("Received CONNACK while in state ClientFinRecv")
        logger.error("Received CONNACK packet while in state ClientFinRecv")
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_info(self, packet):
        raise Exception("Received INFO while in state ClientFinRecv")
        logger.error("Received INFO packet while in state ClientFinRecv")
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

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


class ClientFinSent(ClientState):
    def can_send(self):
        return False

    def can_recv(self):
        return True

    def handle_connack(self, packet):
        raise Exception("Received CONNACK while in state ClientFinSent")
        logger.error("Received CONNACK packet while in state ClientFinSent")
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_info(self, packet):
        self.saw_socket.send_ack_for(packet)

    def handle_ack(self, packet):
        raise Exception("Received ACK while in state ClientFinSent")
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


class ClientSendingFin(ClientState):
    def can_send(self):
        return False

    def can_recv(self):
        return True

    def handle_connect(self, packet):
        logger.error("Received CONNECT packet while in state ServerSendingFin")
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_connack(self, packet):
        logger.error("Received CONNACK packet while in state ServerSendingFin")
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_info(self, packet):
        self.saw_socket.send_ack_for(packet)

    def handle_ack(self, packet):
        pass

    def handle_fin(self, packet):
        # TODO: Se deberia manejar de otra manera pero por ahora lo ignoro
        # self.saw_socket.send_finack_for(packet)
        pass

    def handle_finack(self, packet):
        self.saw_socket.received_finack(packet)
        self.saw_socket.set_state(ClientFinSent(self.saw_socket))

    def close(self):
        raise Exception("Socket closed more than once")


class ClientConnected(ClientState):
    def can_send(self):
        return True

    def can_recv(self):
        return True

    def handle_connack(self, packet):
        #raise Exception("Received CONNACK while in state ClientConnected")
        pass
        #logger.error("Received CONNACK while connected")
        #self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_info(self, packet):
        self.saw_socket.send_ack_for(packet)

    def handle_ack(self, packet):
        self.saw_socket.received_ack(packet)

    def handle_fin(self, packet):
        self.saw_socket.set_state(ClientFinRecv(self.saw_socket))
        self.saw_socket.send_finack_for(packet)

    def handle_finack(self, packet):
        #raise Exception("Received FINACK while in state ClientConnected")
        self.saw_socket.received_finack(packet)

    def close(self):
        self.saw_socket.set_state(ClientSendingFin(self.saw_socket))
        self.saw_socket.send_fin_reliably()


class ClientNotConnected(ClientState):
    def can_send(self):
        return True

    def can_recv(self):
        return False

    def handle_connack(self, packet):
        raise Exception("Received CONNACK while not connected")
        logger.error("Received CONNACK while not connected")
        self.saw_socket.set_state(ClientConnected(self.saw_socket))

    def handle_info(self, packet):
        raise Exception("Received INFO while not connected")
        logger.error("Received INFO while not connected")
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_ack(self, packet):
        raise Exception("Received ACK while not connected")
        logger.error("Received ACK while not connected")
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_fin(self, packet):
        raise Exception("Received FIN while not connected")
        logger.error("Received FIN while not connected")
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def handle_finack(self, packet):
        raise Exception("Received FINACK while not connected")
        logger.error("Received FINACK while not connected")
        self.saw_socket.set_state(ClientDisconnected(self.saw_socket))

    def close(self):
        self.saw_socket.stop()

    def connect(self, addr):
        self.saw_socket.send_connect(addr)
