import logging
import math

logger = logging.getLogger(__name__)

CONNECT = "0"
CONNACK = "1"
INFO = "2"
ACK = "3"
FIN = "4"
FINACK = "5"


class Packet:
    def __init__(self):
        self.type = None
        self.headers = {}
        self.body = None

    @classmethod
    def connack(cls):
        packet = cls()
        packet.type = CONNACK
        return packet

    @classmethod
    def ack(cls):
        packet = cls()
        packet.type = ACK
        return packet

    @classmethod
    def read_from_stream(cls, stream):
        logger.debug("Reading packet from stream")
        packet = cls()
        packet_type_raw = stream.recv_exact(1)
        packet_type = packet_type_raw.decode("utf-8")
        if packet_type == CONNECT:
            if len(packet_type_raw) != 1:
                logger.error("Connect packet has extra data, dropping")
            packet.type = CONNECT
            return packet
        elif packet_type == CONNACK:
            if len(packet_type_raw) != 1:
                logger.error("Connack packet has extra data, dropping")
            packet.type = CONNACK
            return packet
        elif packet_type == INFO:
            packet.type = INFO
            packet.headers["length"] = int.from_bytes(
                stream.recv_exact(16), byteorder="big"
            )
            packet.headers["packet_number"] = int.from_bytes(
                stream.recv_exact(4), byteorder="big"
            )
            logger.debug(
                "Reading packet body (length: %d)", packet.headers["length"]
            )
            packet.body = stream.recv_exact(packet.headers["length"])
            return packet
        elif packet_type == ACK:
            if len(packet_type_raw) != 1:
                logger.error("ACK packet has extra data, dropping")
            packet.type = ACK
            return packet
        elif packet_type == FIN:
            if len(packet_type_raw) != 1:
                logger.error("FIN packet has extra data, dropping")
            packet.type = FIN
            return packet
        elif packet_type == FINACK:
            if len(packet_type_raw) != 1:
                logger.error("FINACK packet has extra data, dropping")
            packet.type = FINACK
            return packet
        else:
            logger.error("Unknown packet type: %s", packet_type)
            raise Exception("Unknown packet type")

    def encode(self):
        if self.type == CONNECT:
            return CONNECT.encode("utf-8")
        elif self.type == CONNACK:
            return CONNACK.encode("utf-8")
        elif self.type == INFO:
            packet_bytes = b""
            packet_bytes += self.type.encode("utf-8")
            packet_bytes += self.headers["length"].to_bytes(
                16, byteorder="big"
            )
            packet_bytes += self.headers["packet_number"].to_bytes(
                4, byteorder="big"
            )
            packet_bytes += self.body
            return packet_bytes
        elif self.type == ACK:
            return ACK.encode("utf-8")
        else:
            raise Exception("Unknown packet type")

    @classmethod
    def divide_buffer(cls, buffer, packet_size):
        packets = []
        for i in range(0, math.ceil(len(buffer) / packet_size)):
            packet = cls()
            packet.type = INFO
            packet.headers["length"] = packet_size
            if i == math.ceil(len(buffer) / packet_size) - 1:
                packet.headers["length"] = len(buffer[i * packet_size :])
            packet.headers["packet_number"] = i
            packet.body = buffer[i * packet_size : (i + 1) * packet_size]
            packets.append(packet)

        return packets

    @classmethod
    def connect(cls):
        packet = cls()
        packet.type = CONNECT
        return packet
