from loguru import logger
import threading
import os
from args_server import args_server
import socket
import sys
import signal

MIN_SIZE = 1024
UPLOAD_SUCCESSFUL_HEADER = 3
CONFIRM_DOWNLOAD_HEADER = 2
ERROR_HEADER = 4
UNKNOWN_TYPE_ERROR = 0
FILE_NOT_FOUND_ERROR = 1
ENDIANESS = "little"

threads = []

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
    type_byte = socket.recv(1)
    type = int.from_bytes(type_byte, byteorder=ENDIANESS)
    logger.debug(f"header type: {str(type)}")

    if type == 0:
        length = int.from_bytes(socket.recv(8), byteorder=ENDIANESS)
        logger.debug(f"file length: {str(length)}")

        filename_length = int.from_bytes(socket.recv(2), byteorder=ENDIANESS)
        logger.debug(f"filename length: {str(filename_length)}")

        filename = socket.recv(filename_length).decode()
        logger.debug(f"filename: {filename}")

        upload_to_server(socket, path, filename, length)

    elif type == 1:
        filename_length = int.from_bytes(socket.recv(2), byteorder=ENDIANESS)
        logger.debug(f"filename length: {str(filename_length)}")

        filename = socket.recv(filename_length).decode()
        logger.debug(f"filename: {filename}")

        download_from_server(socket, path, filename)

    else:
        socket.send((ERROR_HEADER).to_bytes(1, byteorder=ENDIANESS))
        socket.send((UNKNOWN_TYPE_ERROR).to_bytes(1, byteorder=ENDIANESS))

def exit_gracefully(sig, frame):
    signal.signal(signal.SIGINT, original_sigint)

    logger.debug("joining threads")
    for t in threads:
        t.join()

    logger.info("exiting gracefully")
    sys.exit(0)

def start_server():
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

    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.bind((HOST, int(PORT)))

    serverSocket.listen(1)
    logger.info("the server is ready to receive")

    while True:
        connectionSocket, addr = serverSocket.accept()

        if connectionSocket:
            t = threading.Thread(
                target=check_type, args=(connectionSocket, STORAGE)
            )
            threads.append(t)
            t.start()


original_sigint = signal.getsignal(signal.SIGINT)
signal.signal(signal.SIGINT, exit_gracefully)
start_server()
