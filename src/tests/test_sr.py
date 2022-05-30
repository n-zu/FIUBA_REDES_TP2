import pytest
from loguru import logger
from lib.selective_repeat.sr_socket import SRSocket
from lib.rdt_listener.rdt_listener import RDTListener
from threading import Thread


def __client(port, data):
    client = SRSocket()
    client.connect(("127.0.0.1", port))
    client.send(data)
    client.close()


def test_should_receive_data():
    port = 57121
    data = b"hola"
    listener = RDTListener("selective_repeat")
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    thread = Thread(
        target=__client, args=(port, data), name=f"Thread-test-port-{port}"
    )
    thread.start()
    socket = listener.accept()

    output = socket.recv(len(data))
    thread.join()
    socket.close()
    listener.close()

    assert output == data


def test_should_receive_data_big():
    port = 57121 + 1
    data = b"pls_work" * 10000
    listener = RDTListener("selective_repeat")
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    thread = Thread(target=__client, args=(port, data))
    thread.start()
    socket = listener.accept()

    output = socket.recv(len(data))
    thread.join()
    socket.close()
    listener.close()

    assert output == data


def test_should_receive_data_big_buggy():
    port = 57121 + 2
    data = b"".join([x.to_bytes(2, byteorder="little") for x in range(40000)])
    listener = RDTListener("selective_repeat", 0.25)
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    thread = Thread(target=__client, args=[port, data])
    thread.start()
    socket = listener.accept()

    output = socket.recv(len(data))
    thread.join()
    socket.close()
    listener.close()

    assert output == data


def test_should_send_data():
    port = 57121 + 3
    msg = b"Server: Hello"

    listener = RDTListener("selective_repeat")
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    def client(port):
        client = SRSocket()
        client.connect(("127.0.0.1", port))
        cli_msg = client.recv(len(msg))
        assert cli_msg == msg
        client.close()

    thread = Thread(target=client, args=[port])
    thread.start()
    socket = listener.accept()

    socket.send(msg)

    socket.close()
    listener.close()
    thread.join()


def test_should_send_and_receive_data():
    port = 57121 + 4
    msg_1 = b"Client: Hello"
    msg_2 = b"Server: Hello"
    msg_3 = b"Client: Bye"

    listener = RDTListener("selective_repeat")
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    def client(port):
        client = SRSocket()
        client.connect(("127.0.0.1", port))
        client.send(msg_1)
        cli_msg = client.recv(len(msg_2))
        assert cli_msg == msg_2
        client.send(msg_3)
        client.close()

    thread = Thread(target=client, args=[port])
    thread.start()
    socket = listener.accept()

    srv_msg = socket.recv(len(msg_1))
    assert srv_msg == msg_1

    socket.send(msg_2)

    srv_msg = socket.recv(len(msg_3))
    assert srv_msg == msg_3
    thread.join()
    socket.close()
    listener.close()


@pytest.mark.slow
def test_should_receive_data_very_buggy():
    port = 57121 + 5
    data = b"msg"
    listener = RDTListener("selective_repeat", 0.5)
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    thread = Thread(target=__client, args=[port, data])
    thread.start()
    socket = listener.accept()

    output = socket.recv(len(data))
    thread.join()
    socket.close()
    listener.close()

    assert output == data


def test_buggy_client_send():
    port = 57121
    msg = b"IM BUGGY"

    listener = RDTListener("selective_repeat", buggyness_factor=0.5)
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    def client(port):
        client = SRSocket(buggyness_factor=0.5)
        client.connect(("127.0.0.1", port))
        client.send(msg)
        client.close()

    for i in range(10):

        thread = Thread(target=client, args=[port])
        thread.start()
        socket = listener.accept()

        output = socket.recv(len(msg))

        thread.join()
        socket.close()

        logger.success(f"Client {i} Succesfully handled")

    listener.close()
    assert output == msg


if __name__ == "__main__":
    test_buggy_client_send()
