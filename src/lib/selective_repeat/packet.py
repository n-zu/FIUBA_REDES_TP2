import logging
import math

logger = logging.getLogger(__name__)

CONNECT = b"0"
CONNACK = b"1"
INFO = b"2"
ACK = b"3"


class Packet:
    def __init__(self, packet_type):
        self.packet_type = packet_type

    @staticmethod
    def read_from_stream(stream):
        logger.debug("Decoding packet from stream")
        packet_type = stream.recv_exact(1)
        if packet_type == INFO:
            return Info.decode_from_stream(stream)
        if packet_type == ACK:
            return Ack.decode_from_stream(stream)
        if packet_type in (CONNACK, CONNECT):
            return Packet(packet_type)

        raise ValueError(f"Unknown packet type: {type}")

    def encode(self):
        logger.debug(f"Encoding packet of type {self.packet_type}")
        return self.packet_type


class Ack(Packet):
    def __init__(self, number):
        super().__init__(ACK)
        self.__number = number

    @staticmethod
    def decode_from_stream(stream):
        number = int.from_bytes(stream.recv_exact(4), byteorder="big")
        return Ack(number)

    def encode(self):
        bytes = super.encode(self)
        bytes += self.__number.to_bytes(4, byteorder="big")
        return bytes

    def number(self):
        return self.__number


class Info(Packet):
    HEADER_SIZE = 21

    def __init__(self, number, body):
        super().__init__(INFO)
        self.__number = number
        self.__body = body

    @staticmethod
    def decode_from_stream(stream):
        length = int.from_bytes(stream.recv_exact(16), byteorder="big")
        number = int.from_bytes(stream.recv_exact(4), byteorder="big")
        body = stream.recv_exact(length)
        return Info(number, body)

    @classmethod
    def from_buffer(cls, buffer, mtu, initial_number=0):
        packets = []
        mtu = mtu - cls.HEADER_SIZE
        amount = math.ceil(len(buffer) / mtu)
        for i in range(initial_number, initial_number + amount):
            length = mtu
            if i == amount - 1:
                length = len(buffer) - (amount - 1) * mtu

            packet = cls(i, buffer[i * mtu : i * mtu + length])
            packets.append(packet)

        return packets

    def encode(self):
        bytes = super.encode(self)
        bytes += len(self.__body).to_bytes(16, byteorder="big")
        bytes += self.__number.to_bytes(4, byteorder="big")
        bytes += self.__body
        return bytes

    def body(self):
        return self.__body

    def number(self):
        return self.__number
