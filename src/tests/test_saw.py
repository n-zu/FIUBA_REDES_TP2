from lib.rdt_listener.rdt_listener import RDTListener, STOP_AND_WAIT
import threading
import time
from loguru import logger
import sys
from lib.stop_and_wait.saw_socket import SAWSocket

LISTEN_ADDR = ("127.0.0.1", 1234)


config = {
    "handlers": [
        {"sink": sys.stdout, "level": "DEBUG"},
        {"sink": "file.log", "serialize": True},
    ],
}
logger.configure(**config)


def handle_client(stream, recv_length, expected_data):
    data = b""
    stream.settimeout(1)
    while data != expected_data:
        data += stream.recv(recv_length)

    if data != expected_data:
        raise Exception("Data received does not match expected data")
    else:
        logger.success("Received expected data")

    stream.close()


def server_thread(*expected_datas):
    listener = RDTListener(STOP_AND_WAIT)
    listener.bind(LISTEN_ADDR)
    listener.listen(1)

    stream = listener.accept()
    expected_data = expected_datas[0]
    thread = threading.Thread(target=handle_client, args=(stream, len(expected_data.decode("utf-8")), expected_data))
    thread.start()
    thread.join()
    listener.close()


def client_thread(data_to_send):
    socket = SAWSocket()
    socket.connect(LISTEN_ADDR)
    socket.send(bytes(data_to_send))

    socket.close()


def test_one_client_send_small_packet():
    expected_data = b"Hi"
    expected_datas = [expected_data, expected_data]
    thread = threading.Thread(target=server_thread, args=expected_datas)
    thread.start()
    client_thread(expected_data)
    thread.join()


if __name__ == "__main__":
    test_one_client_send_small_packet()
