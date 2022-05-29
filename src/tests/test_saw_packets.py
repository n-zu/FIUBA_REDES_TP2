from unittest.mock import Mock
from lib.selective_repeat.packet import (
    Packet,
    Ack,
    Info,
    Connack,
    Connect,
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
    assert Packet.read_from_stream(mock).type == CONNECT


def test_should_create_connack_packet():
    bytes = CONNACK
    mock = Mock()
    mock.recv.side = bytes
    mock.recv_exact.return_value = bytes
    assert Packet.read_from_stream(mock).type == CONNACK


def test_should_create_ack_packet():
    mock = Mock()
    mock.recv_exact.side_effect = [
        ACK,
        int(43).to_bytes(4, byteorder="big"),
    ]
    packet = Packet.read_from_stream(mock)
    assert packet.type == ACK
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
    assert packet.type == INFO
    assert type(packet) == Info
    assert packet.number() == 4523
    assert packet.body() == arr


def test_create_info_packet():
    packet = Info(366, bytes(b"hello :)"))
    assert packet.type == INFO
    assert packet.number() == 366
    assert packet.body() == b"hello :)"


def test_create_empty_info_packet():
    packet = Info(366, None)
    assert packet.type == INFO
    assert packet.number() == 366
    assert packet.body() is None


def test_create_ack_packet():
    packet = Ack(111)
    assert packet.type == ACK
    assert packet.number() == 111


def test_create_connect_packet():
    packet = Connect()
    assert packet.type == CONNECT


def test_create_connack_packet():
    packet = Connack()
    assert packet.type == CONNACK
