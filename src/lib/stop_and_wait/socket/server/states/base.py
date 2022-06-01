from abc import ABC
from ....states import SAWState
from ....exceptions import ProtocolError


class ServerStateBase(SAWState, ABC):
    def handle_connect(self, packet):
        raise ProtocolError(f"Received CONNECT packet while in state {self}")

    def handle_connack(self, packet):
        raise ProtocolError(f"Received CONNACK while in state {self}")

    def handle_info(self, packet):
        raise ProtocolError(f"Received INFO while in state {self}")

    def handle_ack(self, packet):
        raise ProtocolError(f"Received ACK while in state {self}")

    def handle_fin(self, packet):
        raise ProtocolError(f"Received FIN while in state {self}")

    def handle_finack(self, packet):
        raise ProtocolError(f"Received FINACK while in state {self}")

    def close(self):
        raise Exception(f"Cannot close a socket in state {self}")
