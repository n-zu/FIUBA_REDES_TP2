from abc import ABC
from loguru import logger
from ...states import SAWState


class ServerState(SAWState, ABC):
    def set_disconnected(self):
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))


class ServerDisconnected(ServerState):
    def can_send(self):
        return False

    def can_recv(self):
        return False

    def handle_connect(self, packet):
        raise Exception("Received CONNECT packet while in state ServerDisconnected")
        pass

    def handle_connack(self, packet):
        raise Exception("Received CONNACK while in state ServerDisconnected")
        pass

    def handle_info(self, packet):
        raise Exception("Received INFO while in state ServerDisconnected")
        pass

    def handle_ack(self, packet):
        raise Exception("Received ACK while in state ServerDisconnected")
        pass

    def handle_fin(self, packet):
        raise Exception("Received FIN while in state ServerDisconnected")
        pass

    def handle_finack(self, packet):
        raise Exception("Received FINACK while in state ServerDisconnected")
        pass

    def close(self):
        raise Exception("Cannot close a server socket in disconnected state")


class ServerFinRecv(ServerState):
    def can_send(self):
        return True

    def can_recv(self):
        return False

    def handle_connect(self, packet):
        raise Exception("Received CONNECT while in state ServerFinRecv")
        logger.error("Received CONNECT packet while in state ServerFinRecv")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_connack(self, packet):
        raise Exception("Received CONNACK while in state ServerFinRecv")
        logger.error("Received CONNACK packet while in state ServerFinRecv")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_info(self, packet):
        raise Exception("Received INFO while in state ServerFinRecv")
        logger.error("Received INFO packet while in state ServerFinRecv")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_ack(self, packet):
        self.saw_socket.received_ack(packet)

    def handle_fin(self, packet):
        self.saw_socket.send_finack_for(packet)

    def handle_finack(self, packet):
        self.saw_socket.received_finack(packet)

    def close(self):
        self.saw_socket.send_fin_reliably()
        self.saw_socket.wait_for_fin_retransmission()
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))


class ServerFinSent(ServerState):
    def can_send(self):
        return False

    def can_recv(self):
        return True

    def handle_connect(self, packet):
        logger.error("Received CONNECT packet while in state ServerFinSent")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_connack(self, packet):
        logger.error("Received CONNACK packet while in state ServerFinSent")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_info(self, packet):
        self.saw_socket.send_ack_for(packet)

    def handle_ack(self, packet):
        pass

    def handle_fin(self, packet):
        self.saw_socket.send_finack_for(packet)
        self.saw_socket.wait_for_fin_retransmission()
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_finack(self, packet):
        self.saw_socket.received_finack(packet)

    def close(self):
        raise Exception("Socket closed more than once")


class ServerSendingFin(ServerState):
    def can_send(self):
        return False

    def can_recv(self):
        return True

    def handle_connect(self, packet):
        logger.error("Received CONNECT packet while in state ServerSendingFin")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_connack(self, packet):
        logger.error("Received CONNACK packet while in state ServerSendingFin")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_info(self, packet):
        self.saw_socket.send_ack_for(packet)

    def handle_ack(self, packet):
        pass

    def handle_fin(self, packet):
        # TODO: Se deberia manejar de otra manera pero por ahora lo ignoro
        #self.saw_socket.send_finack_for(packet)
        pass

    def handle_finack(self, packet):
        self.saw_socket.received_finack(packet)
        self.saw_socket.set_state(ServerFinSent(self.saw_socket))

    def close(self):
        raise Exception("Socket closed more than once")


class ServerConnected(ServerState):
    def can_send(self):
        return True

    def can_recv(self):
        return True

    def handle_connect(self, packet):
        logger.error("Received CONNECT packet while in state ServerConnected")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_connack(self, packet):
        logger.error("Received CONNACK packet while in state ServerConnected")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_info(self, packet):
        self.saw_socket.send_ack_for(packet)

    def handle_ack(self, packet):
        self.saw_socket.received_ack(packet)

    def handle_fin(self, packet):
        self.saw_socket.set_state(ServerFinRecv(self.saw_socket))
        self.saw_socket.send_finack_for(packet)

    def handle_finack(self, packet):
        self.saw_socket.received_finack(packet)

    def close(self):
        self.saw_socket.set_state(ServerSendingFin(self.saw_socket))
        self.saw_socket.send_fin_reliably()


class ServerConnecting(ServerState):
    def can_send(self):
        return False

    def can_recv(self):
        return True

    def handle_connect(self, packet):
        self.saw_socket.set_state(ServerConnecting(self.saw_socket))
        self.saw_socket.send_connack_for(packet)

    def handle_connack(self, packet):
        logger.error("Received CONNACK packet while in state ServerConnecting")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

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

    def handle_finack(self, packet):
        logger.error("Received FINACK packet while in state ServerConnecting")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def close(self):
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))


class ServerNotConnected(ServerState):
    def can_send(self):
        return True

    def can_recv(self):
        return False

    def handle_connect(self, packet):
        self.saw_socket.send_connack_for(packet)
        self.saw_socket.set_state(ServerConnecting(self.saw_socket))

    def handle_connack(self, packet):
        logger.error("Received CONNACK packet while in state ServerNotConnected")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_info(self, packet):
        logger.error("Received INFO packet while in state ServerNotConnected")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_ack(self, packet):
        logger.error("Received ACK packet while in state ServerNotConnected")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_fin(self, packet):
        logger.error("Received FIN packet while in state ServerNotConnected")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def handle_finack(self, packet):
        logger.error("Received FINACK packet while in state ServerNotConnected")
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

    def close(self):
        self.saw_socket.set_state(ServerDisconnected(self.saw_socket))

