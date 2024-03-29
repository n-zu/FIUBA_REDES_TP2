import threading
from lib.rdt_listener.rdt_listener import RDTListener
import time
import random
from loguru import logger
import sys

config = {"handlers": [{"sink": sys.stdout, "level": "TRACE"}]}
logger.configure(**config)

LISTEN_ADDR = ("127.0.0.1", 1234)

client_hello = b"".join(
    [x.to_bytes(2, byteorder="little") for x in range(30000)]
)
client_hello_bytes = (
    len(client_hello).to_bytes(4, byteorder="big") + client_hello
)

client_stop = "Stop the server right now"
client_stop_bytes = len(client_stop).to_bytes(4, byteorder="big") + bytes(
    client_stop, "utf-8"
)

welcoming_message = "Hello from server, this is a test"
welcoming_message_bytes = len(welcoming_message).to_bytes(
    4, byteorder="big"
) + bytes(welcoming_message, "utf-8")


def __handle_client(socket, stop):
    try:
        socket.send(welcoming_message_bytes)
        length = int.from_bytes(socket.recv_exact(4), byteorder="big")
        data = socket.recv_exact(length)
        data = data.decode("utf-8")
        if data == client_stop:
            logger.critical("Received stop message")
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
        logger.critical("Client handled")
    except Exception:
        exit(1)


def start_server():
    try:
        listener = RDTListener("stop_and_wait")
        listener.bind(LISTEN_ADDR)
        listener.settimeout(0.1)
        listener.listen(50)
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

        logger.critical("Joining server threads")
        for thread in thread_handlers:
            thread.join()
        logger.critical("Joined server threads")

        listener.close()
        logger.critical("Server finished")
    except Exception:
        exit(1)


def print_threads():
    for thread in threading.enumerate():
        print(thread.__dict__)


def main():
    start_server()
    print_threads()


if __name__ == "__main__":
    main()
