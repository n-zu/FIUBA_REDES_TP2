from lib.selective_repeat.sr_socket import SRSocket
from lib.rdt_listener.rdt_listener import RDTListener
from threading import Thread


def __client(port, data):
    client = SRSocket()
    client.connect(("127.0.0.1", port))
    client.send(data)
    client.stop()


def test_should_receive_data():
    port = 57121
    data = b"hola"
    listener = RDTListener("selective_repeat")
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    thread = Thread(target=__client, args=(port, data))
    thread.start()
    socket = listener.accept()

    output = socket.recv(4)
    socket.stop()
    thread.join()
    listener.close()

    assert output == data


def test_should_receive_random():
    port = 57121 + 1
    n = 2
    data = b"un paquete" * n
    listener = RDTListener("selective_repeat")
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    thread = Thread(target=__client, args=(port, data))
    thread.start()
    socket = listener.accept()

    output = socket.recv(8 * n)
    socket.stop()
    thread.join()
    listener.close()

    assert output == data


if __name__ == "__main__":
    test_should_receive_random()
