import math
from loguru import logger

CONNECT = b"0"
CONNACK = b"1"
INFO = b"2"
ACK = b"3"
FIN = b"4"
FINACK = b"5"

NAMES = {
    b"0": "CONNECT",
    b"1": "CONNACK",
    b"2": "INFO",
    b"3": "ACK",
    b"4": "FIN",
    b"5": "FINACK",
}


class Packet:
    def __init__(self, packet_type=None):
        self.type = packet_type

    @classmethod
    def decode_from_stream(cls, stream):
        return cls()

    @staticmethod
    def read_from_stream(stream):
        packet_type = stream.recv_exact(1)
        logger.debug(
            "Decoding packet of type"
            f" {Packet.get_type_from_byte(packet_type)} from stream"
        )
        if packet_type == INFO:
            return Info.decode_from_stream(stream)
        if packet_type == ACK:
            return Ack.decode_from_stream(stream)
        if packet_type == CONNECT:
            return Connect.decode_from_stream(stream)
        if packet_type == CONNACK:
            return Connack.decode_from_stream(stream)
        if packet_type == FIN:
            return Fin.decode_from_stream(stream)
        if packet_type == FINACK:
            return Finack.decode_from_stream(stream)

        raise ValueError(f"Unknown packet type: {packet_type}")

    @staticmethod
    def get_type_from_byte(byte):
        return NAMES.get(byte, None)

    def encode(self):
        logger.debug(
            f"Encoding packet of type {self.get_type_from_byte(self.type)}"
        )
        return self.type

    def __str__(self):
        return "PACKET"


class Connect(Packet):
    def __init__(self):
        super().__init__(CONNECT)

    @classmethod
    def decode_from_stream(cls, stream):
        return cls()

    def __str__(self):
        return "CONNECT"

    def ack(self):
        return Connack()


class Connack(Packet):
    def __init__(self):
        super().__init__(CONNACK)

    @classmethod
    def decode_from_stream(cls, stream):
        return cls()

    def __str__(self):
        return "CONNACK"


class Ack(Packet):
    def __init__(self, number):
        super().__init__(ACK)
        self.__number = number

    @classmethod
    def decode_from_stream(cls, stream):
        number = int.from_bytes(stream.recv_exact(4), byteorder="big")
        return cls(number)

    def encode(self):
        bytes = super().encode()
        bytes += self.__number.to_bytes(4, byteorder="big")
        return bytes

    def number(self):
        return self.__number

    def __str__(self):
        return f"ACK (number {self.number()})"


class Info(Packet):
    HEADER_SIZE = 21

    def __init__(self, number, body=None):
        super().__init__(INFO)
        self.__number = number
        self.__body = body

    @classmethod
    def decode_from_stream(cls, stream):
        length = int.from_bytes(stream.recv_exact(16), byteorder="big")
        number = int.from_bytes(stream.recv_exact(4), byteorder="big")
        body = stream.recv_exact(length)
        return cls(number, body)

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
        bytes = super().encode()
        size = len(self.__body) if self.__body else 0
        bytes += size.to_bytes(16, byteorder="big")
        bytes += self.__number.to_bytes(4, byteorder="big")
        if self.__body:
            bytes += self.__body
        return bytes

    def body(self):
        return self.__body

    def number(self):
        return self.__number

    def set_number(self, number):
        self.__number = number

    def __str__(self):
        return f"INFO (number {self.number()})"

    def ack(self):
        return Ack(self.number())


class Fin(Packet):
    def __init__(self):
        super().__init__(FIN)

    @classmethod
    def decode_from_stream(cls, stream):
        return cls()

    def __str__(self):
        return "FIN"

    def ack(self):
        return Finack()


class Finack(Packet):
    def __init__(self):
        super().__init__(FINACK)

    @classmethod
    def decode_from_stream(cls, stream):
        return cls()

    def __str__(self):
        return "FINACK"
