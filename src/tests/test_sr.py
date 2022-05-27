from lib.selective_repeat.sr_socket import SRSocket
from lib.rdt_listener.rdt_listener import RDTListener
from threading import Thread
import logging


def __client(port, data):
    client = SRSocket()
    client.connect(("127.0.0.1", port))
    client.send(data)
    client.stop()


logging.basicConfig(level=logging.DEBUG)


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
    data = b"pls_work"
    listener = RDTListener("selective_repeat")
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    thread = Thread(target=__client, args=(port, data))
    thread.start()
    socket = listener.accept()

    output = socket.recv(8)
    socket.stop()
    thread.join()
    listener.close()

    assert output == data


if __name__ == "__main__":
    test_should_receive_data()
