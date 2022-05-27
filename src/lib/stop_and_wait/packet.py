import logging
import math
import socket
from abc import ABC, abstractmethod

from lib.stop_and_wait.exceptions import ProtocolViolation

logger = logging.getLogger(__name__)

from loguru import logger

CONNECT = 0
CONNACK = 1
INFO = 2
ACK = 3
FIN = 4
FINACK = 5


class Packet(ABC):
    @staticmethod
    @abstractmethod
    def read_from_stream(stream):
        pass

    def __bytes__(self):
        pass

    @abstractmethod
    def be_handled_by(self, handler):
        pass


class ConnectPacket(Packet):
    _type = 0

    @classmethod
    def read_from_stream(cls, stream):
        packet = cls()
        return packet

    def __bytes__(self):
        packet_bytes = self._type.to_bytes(1, byteorder="big")
        return packet_bytes

    def be_handled_by(self, handler):
        handler.handle_connect(self)


class ConnackPacket(Packet):
    _type = 1

    @classmethod
    def read_from_stream(cls, stream):
        return cls()

    def __bytes__(self):
        packet_bytes = self._type.to_bytes(1, byteorder="big")
        return packet_bytes

    def be_handled_by(self, handler):
        handler.handle_connack(self)


class InfoPacket(Packet):
    _type = 2

    def __init__(self, number=0, body=b""):
        self.number = number
        self.length = len(body)
        self.body = body

    @property
    def type(self):
        return self._type

    @classmethod
    def read_from_stream(cls, stream):
        packet = cls()
        try:
            packet.length = int.from_bytes(stream.recv_exact(4), byteorder="big")
            packet.number = int.from_bytes(stream.recv_exact(4), byteorder="big")
            packet.body = stream.recv_exact(packet.length)
        except socket.timeout:
            raise ProtocolViolation("Timeout while reading INFO packet")
        return packet

    def __bytes__(self):
        packet_bytes = self._type.to_bytes(1, byteorder="big")
        packet_bytes += self.length.to_bytes(4, byteorder="big")
        packet_bytes += self.number.to_bytes(4, byteorder="big")
        packet_bytes += self.body
        return packet_bytes

    @staticmethod
    def split(mtu, buffer, initial_number=0):
        number_of_packets = math.ceil(len(buffer) / mtu)
        packets = []
        for packet_number in range(initial_number, initial_number + number_of_packets):
            packet = InfoPacket(packet_number, buffer[packet_number * mtu:(packet_number + 1) * mtu])
            packets.append(packet)
        return packets

    def be_handled_by(self, handler):
        handler.handle_info(self)


class AckPacket(Packet):
    _type = 3

    @property
    def type(self):
        return self._type

    @classmethod
    def read_from_stream(cls, stream):
        return cls()

    def __bytes__(self):
        packet_bytes = self._type.to_bytes(1, byteorder="big")
        return packet_bytes

    def be_handled_by(self, handler):
        handler.handle_ack(self)


class FinPacket(Packet):
    _type = 4

    @property
    def type(self):
        return self._type

    @classmethod
    def read_from_stream(cls, stream):
        return cls()

    def __bytes__(self):
        packet_bytes = self._type.to_bytes(1, byteorder="big")
        return packet_bytes

    def be_handled_by(self, handler):
        handler.handle_fin(self)


class FinackPacket(Packet):
    _type = 5



    @property
    def type(self):
        return self._type

    @classmethod
    def read_from_stream(cls, stream):
        return cls()

    def __bytes__(self):
        packet_bytes = self._type.to_bytes(1, byteorder="big")
        return packet_bytes

    def be_handled_by(self, handler):
        handler.handle_finack(self)


def read_packet_type(stream):
    logger.debug("Reading packet type")
    packet_byte_raw = stream.recv_exact(1)
    logger.debug("Packet type read: {}".format(packet_byte_raw))

    return int.from_bytes(packet_byte_raw, byteorder="big")


class PacketFactory:
    @classmethod
    def read_from_stream(cls, stream):
        packet_type = read_packet_type(stream)

        if packet_type == CONNECT:
            return ConnectPacket.read_from_stream(stream)
        if packet_type == CONNACK:
            return ConnackPacket.read_from_stream(stream)
        if packet_type == INFO:
            return InfoPacket.read_from_stream(stream)
        if packet_type == ACK:
            return AckPacket.read_from_stream(stream)
        if packet_type == FIN:
            return FinPacket.read_from_stream(stream)
        if packet_type == FINACK:
            return FinackPacket.read_from_stream(stream)
        raise ValueError(f"Unknown packet type: {packet_type}")

    @classmethod
    def read_connack(cls, stream):
        packet_type = read_packet_type(stream)
        if ConnackPacket._type == packet_type:
            return ConnackPacket.read_from_stream(stream)
        raise ValueError(f"Expected Connack Packet (type {ConnackPacket._type}), got type {packet_type}")


"""
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
        packet = cls()
        packet_type_raw = stream.recv_exact(1)

        packet_type = packet_type_raw.decode("utf-8")
        if packet_type == CONNECT:
            return ConnectPacket.read_from_stream(stream)

        elif packet_type == CONNACK:
            return ConnackPacket.read_from_stream(stream)

        elif packet_type == INFO:
            packet.type = INFO
            try:
                packet.headers["length"] = int.from_bytes(
                    stream.recv_exact(16), byteorder="big"
                )
                packet.headers["packet_number"] = int.from_bytes(
                    stream.recv_exact(4), byteorder="big"
                )
                packet.body = stream.recv_exact(packet.headers["length"])
            except socket.timeout:
                raise ProtocolViolation("Timeout while reading packet")

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
        elif self.type == FIN:
            return FIN.encode("utf-8")
        elif self.type == FINACK:
            return FINACK.encode("utf-8")
        else:
            raise Exception(f"Unknown packet type ({self.type})")

    @classmethod
    def divide_buffer(cls, buffer, packet_size):
        packets = []
        for i in range(0, math.ceil(len(buffer) / packet_size)):
            packet = cls()
            packet.type = INFO
            packet.headers["packet_number"] = i
            if i < math.ceil(len(buffer) / packet_size) - 1:
                packet.body = buffer[i * packet_size:(i + 1) * packet_size]
                packet.headers["length"] = packet_size
            else:
                packet.body = buffer[i * packet_size:]
                packet.headers["length"] = len(buffer[i * packet_size:])

            packets.append(packet)

        return packets

    @classmethod
    def connect(cls):
        packet = cls()
        packet.type = CONNECT
        return packet

    @classmethod
    def fin(cls):
        packet = cls()
        packet.type = FIN
        return packet

    @classmethod
    def finack(cls):
        packet = cls()
        packet.type = FINACK
        return packet
"""