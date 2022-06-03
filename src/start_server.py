import os
import time
import threading
from lib.ftp.args_server import args_server
from lib.rdt_listener.rdt_listener import RDTListener
import signal
import sys
from loguru import logger

threads = []

MIN_SIZE = 30000
CONFIRM_DOWNLOAD = 2
CONFIRM_UPLOAD = 3
ERROR_HEADER = 4

UNKNOWN_TYPE_ERROR = 0
FILE_NOT_FOUND_ERROR = 1
ENDIANESS = "little"

stop_event = threading.Event()


def exit_gracefully(sig, frame):
    signal.signal(signal.SIGINT, original_sigint)

    logger.debug("joining threads")
    for t in threads:
        t.join()

    logger.info("exiting gracefully")
    stop_event.set()


def upload_to_server(socket, path, filename, length):
    logger.info(f"server receiving {filename}")

    if not os.path.exists(path):
        os.makedirs(path)

    counter = 0
    with open(os.path.join(path, filename), "wb") as file:
        while counter < length:
            data = socket.recv(MIN_SIZE)
            file.write(data)
            counter += len(data)

    logger.info(f"server finished receiving {filename}")
    socket.send((CONFIRM_UPLOAD).to_bytes(1, byteorder=ENDIANESS))

    socket.close()


def download_from_server(socket, path, filename):
    length = 0
    try:
        length = os.path.getsize(os.path.join(path, filename))
    except Exception:
        logger.error("file not found")

        error_header_byte = (ERROR_HEADER).to_bytes(1, byteorder=ENDIANESS)
        error_byte = (FILE_NOT_FOUND_ERROR).to_bytes(1, byteorder=ENDIANESS)
        socket.send(error_header_byte + error_byte)

        socket.close()
        return

    logger.info(f"server sending {filename}")

    confirm_byte = (CONFIRM_DOWNLOAD).to_bytes(1, byteorder=ENDIANESS)
    length_byte = (length).to_bytes(8, byteorder=ENDIANESS)
    socket.send(confirm_byte + length_byte)
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
        error_header_byte = (ERROR_HEADER).to_bytes(1, byteorder=ENDIANESS)
        error_byte = (UNKNOWN_TYPE_ERROR).to_bytes(1, byteorder=ENDIANESS)
        socket.send(error_header_byte + error_byte)


def start_server(host, port, storage, method):
    serverSocket = RDTListener(method)
    serverSocket.bind((host, int(port)))
    serverSocket.listen(50)
    serverSocket.settimeout(1)
    logger.info("the server is ready to receive")

    while not stop_event.is_set():
        connectionSocket = serverSocket.accept()

        if connectionSocket:
            t = threading.Thread(
                target=check_type, args=(connectionSocket, storage)
            )
            threads.append(t)
            t.start()
        else:
            # non blocking listener
            time.sleep(0.1)

    logger.info("Server stopped")
    serverSocket.close()
    for t in threads:
        t.join()
    return


if __name__ == "__main__":
    method = "selective_repeat"

    args = args_server()

    logger.remove()
    if args.quiet:
        logger.add(sys.stdout, level="ERROR")
    elif args.verbose:
        logger.add(sys.stdout, level="DEBUG")
        logger.debug("in verbose mode")
    else:
        logger.add(sys.stdout, level="INFO")

    logger.debug("arguments read")

    HOST = args.host
    PORT = args.port
    STORAGE = args.storage

    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, exit_gracefully)
    start_server(HOST, PORT, STORAGE, method)
