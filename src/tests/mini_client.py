import threading
from lib.rdt_listener.rdt_listener import RDTListener
from lib.stop_and_wait.saw_socket import SAWSocket
from lib.selective_repeat.sr_socket import SRSocket
import time
import random
from loguru import logger
import sys

config = {
    "handlers": [
        {"sink": sys.stdout, "level": "TRACE"},
    ],
}
logger.configure(**config)

LISTEN_ADDR = ("127.0.0.1", 1234)

client_hello = "Hello from client"
client_hello_bytes = len(client_hello).to_bytes(4, byteorder="big") + bytes(client_hello, "utf-8")
client_stop = "Stop the server right now"
client_stop_bytes = len(client_stop).to_bytes(4, byteorder="big") + bytes(client_stop, "utf-8")

welcoming_message = "Hello from server, this is a test"
welcoming_message_bytes = len(welcoming_message).to_bytes(4, byteorder="big") + bytes(welcoming_message, "utf-8")


def start_client():
    socket = SAWSocket(buggyness_factor=0.5)
    socket.connect(LISTEN_ADDR)
    length = int.from_bytes(socket.recv_exact(4), byteorder="big")
    data = socket.recv_exact(length)
    data = data.decode("utf-8")
    if data != welcoming_message:
        raise Exception(f"Data received does not match expected data (expected {welcoming_message}, got {data})")
    else:
        logger.success("Received welcoming message")

    socket.send(client_hello_bytes)
    """
    if random.randint(0, 1) == 0:
        socket.send(client_hello_bytes)
        length = int.from_bytes(socket.recv_exact(4), byteorder="big")
        data = socket.recv_exact(length)
        data = data.decode("utf-8")
        if data != welcoming_message:
            raise Exception("Data received does not match expected data")
        else:
            logger.success("Received welcoming message")
    else:
        length = int.from_bytes(socket.recv_exact(4), byteorder="big")
        data = socket.recv_exact(length)
        data = data.decode("utf-8")
        if data != welcoming_message:
            raise Exception(f"Data received does not match expected data (expected {welcoming_message}, got {data})")
        else:
            logger.success("Received welcoming message")

        socket.send(client_hello_bytes)
    """
    time.sleep(random.random() * 5)
    socket.close()
    logger.critical("Client finished")


def stopper_client():
    socket = SAWSocket(buggyness_factor=0.2)
    socket.connect(LISTEN_ADDR)
    logger.info("Sending stop message")
    socket.send(client_stop_bytes)

    time.sleep(random.random() * 5)
    socket.close()
    logger.critical("Stopper client finished")


def main():
    threads = []
    for i in range(10):
        client_thread = threading.Thread(target=start_client)
        client_thread.start()
        threads.append(client_thread)

    for thread in threads:
        thread.join()
    stopper_client()
    time.sleep(60)
    for thread in threading.enumerate():
        print(thread.__dict__)


if __name__ == "__main__":
    main()

