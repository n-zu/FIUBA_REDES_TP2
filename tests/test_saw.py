import logging
import sys
import os

from .lib.rdt.stop_and_wait.saw_socket import SAWSocket

#from src.lib.rdt.stop_and_wait.saw_socket import SAWSocket

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

if __name__ == "__main__":
    socket = SAWSocket()
    socket.connect(("127.0.0.1", 1234))
    socket.send(b"Hello World, this is a test, but a longer one")

