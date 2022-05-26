import logging
import time

from lib.rdt_listener.rdt_listener import RDTListener, STOP_AND_WAIT

logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    listener = RDTListener(STOP_AND_WAIT)

    listener.bind(("127.0.0.1", 1234))
    listener.listen(1)

    time.sleep(1)
    stream = listener.accept()
    logging.debug("Accepted new connection")
    # stream.send(b"Hello from server")
    data = b""
    while data != b"Hello World, this is a test, but a longer one":
        data += stream.recv(4096)

    logging.debug(f"Received {data.decode()} from client")
    stream.send(b"Hello from server")

    stream.close()
    logging.debug("Closed connection")
    exit()
