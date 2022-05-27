import logging
import sys
import threading
import time
from loguru import logger

from lib.stop_and_wait.saw_socket import SAWSocket
from lib.mux_demux.mux_demux_stream import MuxDemuxStream

config = {
    "handlers": [
        {"sink": sys.stdout, "level": "DEBUG"},
        {"sink": "file.log", "serialize": True},
    ],
}
logger.configure(**config)

if __name__ == "__main__":
    socket = SAWSocket()
    socket.connect(("127.0.0.1", 1234))
    """
    socket.send(b"Hello from client, this is a test, please ignore")

    data = b""
    while data != b"Hello from server":
        data += socket.recv(4096)
    logger.debug(f"Received {data.decode()} from server")

    time.sleep(5)
    """
    time.sleep(10)
    socket.close()
    logger.debug("Closed connection")

    """
        data = b""
        while data != b"Hello from server":
            logging.debug(f"Received {data.decode()} from client")
            data += socket.recv(4096)

        logging.debug(f"Received {data.decode()} from server")
    """