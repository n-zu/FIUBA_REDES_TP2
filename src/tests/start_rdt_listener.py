import logging
import threading
import time
from loguru import logger
import sys

from lib.rdt_listener.rdt_listener import RDTListener, STOP_AND_WAIT
from lib.mux_demux.mux_demux_listener import MuxDemuxListener


config = {
    "handlers": [
        {"sink": sys.stdout, "level": "DEBUG"},
    ],
}
logger.configure(**config)


if __name__ == "__main__":
    listener = RDTListener(STOP_AND_WAIT)

    listener.bind(("127.0.0.1", 1234))
    listener.listen(1)

    logger.debug("Waiting for connection")
    stream = listener.accept()
    time.sleep(5)
    stream.close()
    listener.close()


    """
    stream.settimeout(1)
    logging.debug("Accepted new connection")
    # stream.send(b"Hello from server")
    data = b""
    while data != b"Hello from client, this is a test, please ignore":
        logging.debug(f"Received {data.decode()} from client")
        data += stream.recv(4096)

    logger.debug(f"Received {data.decode()} from client")
    #stream.send(b"Hello from server")

    stream.send(b"Hello from server")

    stream.close()
    logging.debug("Closed connection")
    time.sleep(2)
    exit()
    """