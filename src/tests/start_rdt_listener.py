import random
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


def new_handle_client(stream):
    logger.critical("Sending data to client")
    stream.send(b"Hello from server, this is a test, please ignore")
    time.sleep(random.random() * 5)
    stream.close()


def main():
    listener = RDTListener(STOP_AND_WAIT)

    listener.bind(("127.0.0.1", 1234))
    listener.listen(5)
    threads = []
    for i in range(1):
        stream = listener.accept()
        logger.critical("Stream accepted")
        thread = threading.Thread(target=new_handle_client, args=(stream, ))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()
    listener.close()


if __name__ == "__main__":
    main()
