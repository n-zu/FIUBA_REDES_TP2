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
    listener = RDTListener("selective_repeat", 0.20)
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    thread = Thread(target=__client, args=(port, data))
    thread.start()
    socket = listener.accept()

    output = socket.recv(len(data))
    # Como todavia no esta el FIN y FINACK hay que joinear
    # el otro thread antes de cerrar este socket
    thread.join()
    socket.close()
    listener.close()

    assert output == data


if __name__ == "__main__":
    test_should_receive_data_big_buggy()
