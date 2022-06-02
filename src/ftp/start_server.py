import os
import time
import threading
from ftp.args_server import args_server
from lib.rdt_listener.rdt_listener import RDTListener
import signal
import sys
from loguru import logger


MIN_SIZE = 1024
UPLOAD_SUCCESSFUL_HEADER = 3
CONFIRM_DOWNLOAD_HEADER = 2
ERROR_HEADER = 4
UNKNOWN_TYPE_ERROR = 0
FILE_NOT_FOUND_ERROR = 1
ENDIANESS = "little"


def signal_handler(sig, frame, stop_event):
    stop_event.set()


def upload_to_server(socket, path, filename, length):
    logger.info(f"server receiving {filename}")

    counter = 0
    with open(os.path.join(path, filename), "wb") as file:
        while counter < length:
            data = socket.recv(MIN_SIZE)
            file.write(data)
            counter += len(data)

    logger.info(f"server finished receiving {filename}")
    socket.send((UPLOAD_SUCCESSFUL_HEADER).to_bytes(1, byteorder=ENDIANESS))

    socket.close()


def download_from_server(socket, path, filename):
    length = 0
    try:
        length = os.path.getsize(os.path.join(path, filename))
    except Exception:
        logger.error("file not found")

        socket.send((ERROR_HEADER).to_bytes(1, byteorder=ENDIANESS))
        socket.send((FILE_NOT_FOUND_ERROR).to_bytes(1, byteorder=ENDIANESS))

        socket.close()
        return

    logger.info(f"server sending {filename}")

    socket.send((CONFIRM_DOWNLOAD_HEADER).to_bytes(1, byteorder=ENDIANESS))
    socket.send((length).to_bytes(8, byteorder=ENDIANESS))
    logger.debug(f"file length: {str(length)}")

    counter = 0
    with open(os.path.join(path, filename), "rb") as file:
        while counter < length:
            data = file.read(MIN_SIZE)
            socket.send(data)
            counter += len(data)

    logger.info(f"server finished sending {filename}")

    socket.close()


def check_type(socket, path):
    type_byte = socket.recv_exact(1)
    type = int.from_bytes(type_byte, byteorder=ENDIANESS)
    logger.debug(f"header type: {str(type)}")

    if type == 0:
        length = int.from_bytes(socket.recv_exact(8), byteorder=ENDIANESS)
        logger.debug(f"file length: {str(length)}")

        filename_length = int.from_bytes(
            socket.recv_exact(2), byteorder=ENDIANESS
        )
        logger.debug(f"filename length: {str(filename_length)}")

        filename = socket.recv_exact(filename_length).decode()
        logger.debug(f"filename: {filename}")

        upload_to_server(socket, path, filename, length)

    elif type == 1:
        filename_length = int.from_bytes(
            socket.recv_exact(2), byteorder=ENDIANESS
        )
        logger.debug(f"filename length: {str(filename_length)}")

        filename = socket.recv_exact(filename_length).decode()
        logger.debug(f"filename: {filename}")

        download_from_server(socket, path, filename)

    else:
        socket.send((ERROR_HEADER).to_bytes(1, byteorder=ENDIANESS))
        socket.send((UNKNOWN_TYPE_ERROR).to_bytes(1, byteorder=ENDIANESS))


def start_server(host, port, storage, method):

    serverSocket = RDTListener(method)
    serverSocket.bind((host, int(port)))
    serverSocket.listen(50)
    serverSocket.settimeout(1)
    logger.info("the server is ready to receive")

    stop_event = threading.Event()

    if threading.current_thread().__class__.__name__ == '_MainThread':
        signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, stop_event))

    threads = []
    while not stop_event.is_set():
        connectionSocket = serverSocket.accept()

        if connectionSocket:
            t = threading.Thread(
                target=check_type, args=(connectionSocket, storage)
            )
            threads.append(t)
            t.start()
            # TODO: join finished threads before server close (?)
        else:
            # non blocking listener
            time.sleep(0.1)

    logger.info("Server stopped")
    serverSocket.close()
    for t in threads:
        t.join()
    return


if __name__ == "__main__":
    method = "stop_and_wait"

    args = args_server()

    logger.remove()
    if args.quiet:
        logger.add(sys.stdout, level='ERROR')
    elif args.verbose:
        logger.add(sys.stdout, level='DEBUG')
        logger.debug("in verbose mode")
    else:
        logger.add(sys.stdout, level='INFO')

    logger.debug("arguments read")

    HOST = args.host
    PORT = args.port
    STORAGE = args.storage

    start_server(HOST, PORT, STORAGE, method)

