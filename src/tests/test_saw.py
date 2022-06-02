import time

from lib.rdt_listener.rdt_listener import RDTListener, STOP_AND_WAIT
import threading
from loguru import logger
import sys
from lib.stop_and_wait.saw_socket import SAWSocket

LISTEN_ADDR = ("127.0.0.1", 1234)


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
    thread = threading.Thread(
        target=handle_client,
        args=(stream, len(expected_data.decode("utf-8")), expected_data),
    )
    thread.start()
    thread.join()
    listener.close()


def __client(port, data):
    client = SAWSocket()
    client.connect(("127.0.0.1", port))
    client.send(data)
    client.close()


def test_should_receive_data_big_buggy():
    port = 57121 + 2
    data = b"".join([x.to_bytes(2, byteorder="little") for x in range(400)])
    listener = RDTListener("stop_and_wait", 0.20)
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    thread = threading.Thread(target=__client, args=(port, data))
    thread.start()
    socket = listener.accept()

    output = socket.recv_exact(len(data))

    # Si intercambias estas 2 lineas de lugar muere:
    socket.close()
    thread.join()

    time.sleep(15)
    listener.close()
    assert output == data


if __name__ == "__main__":
    test_should_receive_data_big_buggy()
