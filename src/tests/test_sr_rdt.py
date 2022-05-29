from lib.selective_repeat.sr_socket import SRSocket
from lib.rdt_listener.rdt_listener import RDTListener
from threading import Thread


def test_should_receive_data_from_multiple_clients():
    port = 57121
    data_1 = b"Client 1"
    data_2 = b"Client 2"
    listener = RDTListener("selective_repeat")
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    def client(port, data):
        client = SRSocket()
        client.connect(("127.0.0.1", port))
        client.send(data)
        client.close()

    thread_1 = Thread(
        target=client, args=(port, data_1), name=f"Thread-test-port-{port}"
    )
    thread_1.start()
    socket_1 = listener.accept()

    thread_2 = Thread(
        target=client, args=(port, data_2), name=f"Thread-test-port-{port}"
    )
    thread_2.start()
    socket_2 = listener.accept()

    output_1 = socket_1.recv(len(data_1))
    thread_1.join()
    socket_1.close()

    output_2 = socket_2.recv(len(data_2))
    thread_2.join()
    socket_2.close()

    listener.close()

    assert output_1 == data_1
    assert output_2 == data_2


def test_should_send_and_receive_data_from_multiple_clients():
    port = 57121 + 1
    data_1 = b"Client 1"
    data_2 = b"Client 2"
    server_message = b"Please Disconnect"
    client_response = b"Bye"
    listener = RDTListener("selective_repeat", 0.20)
    listener.bind(("127.0.0.1", port))
    listener.listen(1)

    def client(port, data):
        client = SRSocket()
        client.connect(("127.0.0.1", port))
        client.send(data)
        msg = client.recv(len(server_message))
        client.send(client_response)
        client.close()
        assert msg == server_message

    thread_1 = Thread(
        target=client, args=(port, data_1), name=f"Thread-test-port-{port}"
    )
    thread_1.start()
    socket_1 = listener.accept()

    thread_2 = Thread(
        target=client, args=(port, data_2), name=f"Thread-test-port-{port}"
    )
    thread_2.start()
    socket_2 = listener.accept()

    output_1 = socket_1.recv(len(data_1))
    socket_1.send(server_message)
    socket_1.recv(len(client_response))
    thread_1.join()
    socket_1.close()

    output_2 = socket_2.recv(len(data_2))
    socket_2.send(server_message)
    socket_2.recv(len(client_response))
    thread_2.join()
    socket_2.close()

    listener.close()

    assert output_1 == data_1
    assert output_2 == data_2
