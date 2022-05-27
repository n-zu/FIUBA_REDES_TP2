import logging
import sys
import time

from lib.stop_and_wait.saw_socket import SAWSocket
from lib.mux_demux.mux_demux_stream import MuxDemuxStream

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

if __name__ == "__main__":
    socket = SAWSocket()
    socket.connect(("127.0.0.1", 1234))
    socket.settimeout(None)
    socket.send(b"Hello from client, this is a test, please ignore")

    time.sleep(5)
    socket.close()
    logging.debug("Closed connection")

    """
        data = b""
        while data != b"Hello from server":
            logging.debug(f"Received {data.decode()} from client")
            data += socket.recv(4096)

        logging.debug(f"Received {data.decode()} from server")
    """