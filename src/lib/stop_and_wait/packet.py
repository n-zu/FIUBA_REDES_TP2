from math import ceil
import socket
from abc import ABC, abstractmethod
from .exceptions import ProtocolError

CONNECT = b"0"
CONNACK = b"1"
INFO = b"2"
ACK = b"3"
FIN = b"4"
FINACK = b"5"


class Packet(ABC):
    def __repr__(self):
        return self.__class__.__name__

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
    type = CONNECT

    @classmethod
    def read_from_stream(cls, stream):
        packet = cls()
        return packet

    def __bytes__(self):
        packet_bytes = self.type
        return packet_bytes

    def be_handled_by(self, handler):
        handler.handle_connect(self)


class ConnackPacket(Packet):
    type = CONNACK

    @classmethod
    def read_from_stream(cls, stream):
        return cls()

    def __bytes__(self):
        packet_bytes = self.type
        return packet_bytes

    def be_handled_by(self, handler):
        handler.handle_connack(self)


class InfoPacket(Packet):
    MAX_SPLIT_NUMBER = 2**16
    type = INFO

    def __init__(self, number=0, body=b""):
        self.number = number
        self.body = body if body else b""
        self.length = len(self.body)

    @classmethod
    def read_from_stream(cls, stream):
        packet = cls()
        try:
            packet.length = int.from_bytes(
                stream.recv_exact(4), byteorder="big"
            )
            packet.number = int.from_bytes(
                stream.recv_exact(4), byteorder="big"
            )
            packet.body = stream.recv_exact(packet.length)
        except socket.timeout:
            raise ProtocolError("Timeout while reading INFO packet")
        return packet

    def __bytes__(self):
        packet_bytes = self.type
        packet_bytes += self.length.to_bytes(4, byteorder="big")
        packet_bytes += self.number.to_bytes(4, byteorder="big")
        packet_bytes += self.body
        return packet_bytes

    @classmethod
    def split(cls, mtu, buffer, initial_number=0):
        if len(buffer) <= mtu:
            return [InfoPacket(initial_number, buffer)]

        number_of_packets = ceil(len(buffer) / mtu)
        packets = []
        for i in range(number_of_packets):
            packet = InfoPacket(
                (i + initial_number) % cls().MAX_SPLIT_NUMBER,
                buffer[i * mtu : (i + 1) * mtu],
            )
            packets.append(packet)
        return packets

    def be_handled_by(self, handler):
        handler.handle_info(self)


class AckPacket(Packet):
    type = ACK

    def __init__(self, number):
        self.number = number

    @classmethod
    def read_from_stream(cls, stream):
        number = int.from_bytes(stream.recv_exact(4), byteorder="big")
        return cls(number)

    def __bytes__(self):
        packet_bytes = self.type
        packet_bytes += self.number.to_bytes(4, byteorder="big")
        return packet_bytes

    def be_handled_by(self, handler):
        handler.handle_ack(self)


class FinPacket(Packet):
    type = FIN

    @classmethod
    def read_from_stream(cls, stream):
        return cls()

    def __bytes__(self):
        packet_bytes = self.type
        return packet_bytes

    def be_handled_by(self, handler):
        handler.handle_fin(self)


class FinackPacket(Packet):
    type = FINACK

    @classmethod
    def read_from_stream(cls, stream):
        return cls()

    def __bytes__(self):
        packet_bytes = self.type
        return packet_bytes

    def be_handled_by(self, handler):
        handler.handle_finack(self)


class PacketFactory:
    @classmethod
    def read_from_stream(cls, stream):
        packet_type = stream.recv_exact(1)

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
        packet_type = stream.recv_exact(1)
        if ConnackPacket.type == packet_type:
            return ConnackPacket.read_from_stream(stream)
        raise ValueError(
            f"Expected Connack Packet (type {ConnackPacket.type}), got type"
            f" {packet_type}"
        )

    @classmethod
    def read_ack(cls, stream):
        packet_type = stream.recv_exact(1)
        if AckPacket.type == packet_type:
            return AckPacket.read_from_stream(stream)
        raise ValueError(
            f"Expected Ack Packet (type {AckPacket.type}), got type"
            f" {packet_type}"
        )
