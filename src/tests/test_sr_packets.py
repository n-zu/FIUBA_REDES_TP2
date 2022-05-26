from unittest.mock import Mock
from lib.selective_repeat.packet import (
    Packet,
    Ack,
    Info,
    CONNECT,
    CONNACK,
    INFO,
    ACK,
)


def test_should_create_connect_packet():
    bytes = CONNECT
    mock = Mock()
    mock.recv.return_value = bytes
    mock.recv_exact.return_value = bytes
    assert Packet.read_from_stream(mock).packet_type == CONNECT


def test_should_create_connack_packet():
    bytes = CONNACK
    mock = Mock()
    mock.recv.side = bytes
    mock.recv_exact.return_value = bytes
    assert Packet.read_from_stream(mock).packet_type == CONNACK


def test_should_create_ack_packet():
    mock = Mock()
    mock.recv_exact.side_effect = [
        ACK,
        int(43).to_bytes(4, byteorder="big"),
    ]
    packet = Packet.read_from_stream(mock)
    assert packet.packet_type == ACK
    assert type(packet) == Ack
    assert packet.number() == 43


def test_should_create_info_packet():
    mock = Mock()
    arr = bytes(range(100)) + b"hola soy ser..."
    mock.recv_exact.side_effect = [
        INFO,
        int(100).to_bytes(16, byteorder="big"),
        int(4523).to_bytes(4, byteorder="big"),
        arr,
    ]
    packet = Packet.read_from_stream(mock)
    assert packet.packet_type == INFO
    assert type(packet) == Info
    assert packet.number() == 4523
    assert packet.body() == arr


def test_create_info_packet():
    packet = Info(366, bytes(b"hello :)"))
    assert packet.packet_type == INFO
    assert packet.number() == 366
    assert packet.body() == b"hello :)"


def test_create_ack_packet():
    packet = Ack(111)
    assert packet.packet_type == ACK
    assert packet.number() == 111


def test_create_connect_packet():
    packet = Packet(CONNECT)
    assert packet.packet_type == CONNECT


def test_create_connack_packet():
    packet = Packet(CONNACK)
    assert packet.packet_type == CONNACK
