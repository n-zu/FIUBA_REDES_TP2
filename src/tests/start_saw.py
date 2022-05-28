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
    socket.settimeout(1)

    data = b""
    while data != b"Hello from server, this is a test, please ignore":
        data += socket.recv(4096)
        logger.critical(f"Received data: {data}")
        time.sleep(0.5)
        logger.debug(data)

    logger.success(f"Received expected data: {data}")

    socket.close()
    logger.success("Closed connection")
