import threading
from lib.rdt_listener.rdt_listener import RDTListener
from lib.selective_repeat.sr_socket import SRSocket
import time
import random
from loguru import logger

LISTEN_ADDR = ("127.0.0.1", 1234)
BUGGY = 0.3
CLIENTS = 5

client_hello = "Hello from client"
client_hello_bytes = len(client_hello).to_bytes(4, byteorder="big") + bytes(
    client_hello, "utf-8"
)
client_stop = "Stop the server right now"
client_stop_bytes = len(client_stop).to_bytes(4, byteorder="big") + bytes(
    client_stop, "utf-8"
)

welcoming_message = "Hello from server, this is a test, please ignore"
welcoming_message_bytes = len(welcoming_message).to_bytes(
    4, byteorder="big"
) + bytes(welcoming_message, "utf-8")


def __handle_client(socket, stop):
    socket.send(welcoming_message_bytes)
    length = int.from_bytes(socket.recv(4), byteorder="big")
    data = socket.recv(length)
    data = data.decode("utf-8")
    if data == client_stop:
        logger.success("Received stop message")
        stop.set()
    elif data != client_hello:
        raise Exception(
            "Data received does not match expected data (expected"
            f" {client_hello}, got {data})"
        )
    else:
        logger.success("Received client hello")

    time.sleep(random.random() * 5)
    socket.close()
    logger.success("Client handled")


def start_server(
    protocol,
):
    listener = RDTListener(protocol, buggyness_factor=BUGGY)
    listener.setblocking(False)
    listener.bind(LISTEN_ADDR)
    listener.listen(50)
    logger.success(f"Started {protocol} Server on {LISTEN_ADDR}")
    thread_handlers = []

    stop = threading.Event()
    while not stop.is_set():
        socket = listener.accept()
        if socket is not None:
            thread = threading.Thread(
                target=__handle_client, args=(socket, stop)
            )
            thread.start()
            thread_handlers.append(thread)
        else:
            time.sleep(0.1)

    logger.success("Joining server threads")
    for thread in thread_handlers:
        thread.join()
    logger.success("Joined server threads")

    listener.close()
    logger.success("Server finished")


def start_client(i):
    logger.success(f"Starting client {i}")
    socket = SRSocket(buggyness_factor=BUGGY)
    socket.connect(LISTEN_ADDR)
    if i % 2 == 0:
        socket.send(client_hello_bytes)

    length = int.from_bytes(socket.recv(4), byteorder="big")
    data = socket.recv(length)
    data = data.decode("utf-8")
    if data != welcoming_message:
        raise Exception("Data received does not match expected data")
    else:
        logger.success("Received welcoming message")

    if i % 2 == 1:
        socket.send(client_hello_bytes)

    time.sleep(random.random() * 5)
    socket.close()
    logger.success("Client finished")


def stopper_client():
    socket = SRSocket(buggyness_factor=BUGGY)
    socket.connect(LISTEN_ADDR)
    logger.info("Sending stop message")
    socket.send(client_stop_bytes)

    time.sleep(random.random() * 5)
    socket.close()
    logger.success("Stopper client finished")


def main():
    server_thread = threading.Thread(
        target=start_server, args=["selective_repeat"]
    )
    server_thread.start()

    threads = []
    for i in range(CLIENTS - 1):
        client_thread = threading.Thread(target=start_client, args=[i])
        client_thread.start()
        threads.append(client_thread)

    for thread in threads:
        thread.join()

    stopper_client()
    server_thread.join()

    logger.success("All finished")


if __name__ == "__main__":
    main()
