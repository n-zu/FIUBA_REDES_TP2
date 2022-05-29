import threading
from lib.rdt_listener.rdt_listener import RDTListener
from lib.stop_and_wait.saw_socket import SAWSocket
from lib.selective_repeat.sr_socket import SRSocket
import time
import random
from loguru import logger

LISTEN_ADDR = ("127.0.0.1", 1234)

client_hello = "Hello from client"
client_hello_bytes = len(client_hello).to_bytes(4, byteorder="big") + bytes(client_hello, "utf-8")
client_stop = "Stop the server right now"
client_stop_bytes = len(client_stop).to_bytes(4, byteorder="big") + bytes(client_stop, "utf-8")

welcoming_message = "Hello from server, this is a test, please ignore"
welcoming_message_bytes = len(welcoming_message).to_bytes(4, byteorder="big") + bytes(welcoming_message, "utf-8")


def __handle_client(socket, stop):
    socket.send(welcoming_message_bytes)
    length = int.from_bytes(socket.recv(4), byteorder="big")
    data = socket.recv_exact(length)
    data = data.decode("utf-8")
    if data == client_stop:
        logger.critical("Received stop message")
        stop.set()
    elif data != client_hello:
        raise Exception(f"Data received does not match expected data (expected {client_hello}, got {data})")
    else:
        logger.success("Received client hello")

    time.sleep(random.random() * 5)
    socket.close()
    logger.critical("Client handled")


def start_server():
    listener = RDTListener("stop_and_wait", buggyness_factor=0.2)
    listener.bind(LISTEN_ADDR)
    listener.listen(50)
    listener.settimeout(5)
    thread_handlers = []

    stop = threading.Event()
    while not stop.is_set():
        socket = listener.accept()
        if socket is not None:
            thread = threading.Thread(target=__handle_client, args=(socket, stop))
            thread.start()
            thread_handlers.append(thread)

    logger.critical("Joining server threads")
    for thread in thread_handlers:
        thread.join()
    logger.critical("Joined server threads")

    listener.close()
    logger.critical("Server finished")


def start_client():
    socket = SAWSocket(buggyness_factor=0.2)
    socket.connect(LISTEN_ADDR)
    socket.setblocking(True)
    socket.settimeout(None)
    if random.randint(0, 1) == 0:
        socket.send(client_hello_bytes)
        length = int.from_bytes(socket.recv(4), byteorder="big")
        data = socket.recv_exact(length)
        data = data.decode("utf-8")
        if data != welcoming_message:
            raise Exception("Data received does not match expected data")
        else:
            logger.success("Received welcoming message")
    else:
        length = int.from_bytes(socket.recv(4), byteorder="big")
        data = socket.recv_exact(length)
        data = data.decode("utf-8")
        if data != welcoming_message:
            raise Exception(f"Data received does not match expected data (expected {welcoming_message}, got {data})")
        else:
            logger.success("Received welcoming message")

        socket.send(client_hello_bytes)

    time.sleep(random.random() * 5)
    socket.close()
    logger.critical("Client finished")


def stopper_client():
    socket = SAWSocket(buggyness_factor=0.2)
    socket.connect(LISTEN_ADDR)
    socket.setblocking(True)
    socket.settimeout(None)
    logger.info("Sending stop message")
    socket.send(client_stop_bytes)

    time.sleep(random.random() * 5)
    socket.close()
    logger.critical("Stopper client finished")


def main():
    server_thread = threading.Thread(target=start_server)
    server_thread.start()

    threads = []
    for i in range(1):
        client_thread = threading.Thread(target=start_client)
        client_thread.start()
        threads.append(client_thread)

    for thread in threads:
        thread.join()

    stopper_client()
    server_thread.join()

    time.sleep(10)
    for thread in threading.enumerate():
        print(thread.__dict__)


if __name__ == "__main__":
    main()
