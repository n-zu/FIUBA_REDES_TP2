from lib.selective_repeat.sr_socket import SRSocket
from lib.rdt_listener.rdt_listener import RDTListener
from threading import Thread
import logging


def __client():
    client = SRSocket()
    client.connect(("127.0.0.1", 57121))
    client.send(b"hola")
    client.stop()


logging.basicConfig(level=logging.DEBUG)


def test_should_receive_data():
    listener = RDTListener("selective_repeat")
    listener.bind(("127.0.0.1", 57121))
    listener.listen(1)

    thread = Thread(target=__client)
    thread.start()
    socket = listener.accept()

    output = socket.recv(4)
    socket.stop()
    thread.join()
    listener.close()

    assert output == b"hola"


if __name__ == "__main__":
    test_should_receive_data()
