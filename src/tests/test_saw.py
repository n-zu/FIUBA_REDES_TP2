from lib.rdt_listener.rdt_listener import RDTListener, STOP_AND_WAIT
import threading
import time

from lib.stop_and_wait.saw_socket import SAWSocket

LISTEN_ADDR = ("127.0.0.1", 1234)


def handle_client(stream, recv_length, expected_data):
    data = b""
    while data != expected_data:
        data += stream.recv(recv_length)

    assert data == expected_data


def server_thread(expected_datas):
    listener = RDTListener(STOP_AND_WAIT)
    listener.bind(LISTEN_ADDR)
    listener.listen(1)

    stream = listener.accept()
    expected_data = expected_datas[0]
    thread = threading.Thread(target=handle_client, args=(stream, len(expected_data), expected_data))
    thread.start()


def client_thread(data_to_send):
    socket = SAWSocket()
    socket.connect(LISTEN_ADDR)
    socket.send(data_to_send)


def test_one_client_send_small_packet():
    expected_data = b"Hi"
    thread = threading.Thread(target=server_thread, args=([expected_data]))
    thread.start()

    client_thread(expected_data)
    time.sleep(2)

