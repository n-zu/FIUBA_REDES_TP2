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
        for i in range(number_of_packets):
            packet = InfoPacket(i + initial_number, buffer[i * mtu:(i + 1) * mtu])
            packets.append(packet)
        return packets

    def be_handled_by(self, handler):
        handler.handle_info(self)


class AckPacket(Packet):
    _type = 3

    def __init__(self, number):
        self.number = number

    @property
    def type(self):
        return self._type

    @classmethod
    def read_from_stream(cls, stream):
        number = int.from_bytes(stream.recv_exact(4), byteorder="big")
        return cls(number)

    def __bytes__(self):
        packet_bytes = self._type.to_bytes(1, byteorder="big")
        packet_bytes += self.number.to_bytes(4, byteorder="big")
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
    packet_byte = int.from_bytes(packet_byte_raw, byteorder="big")
    logger.debug("Packet type read: {}".format(packet_byte))

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

    @classmethod
    def read_ack(cls, stream):
        packet_type = read_packet_type(stream)
        if AckPacket._type == packet_type:
            return AckPacket.read_from_stream(stream)
        raise ValueError(f"Expected Ack Packet (type {AckPacket._type}), got type {packet_type}")
