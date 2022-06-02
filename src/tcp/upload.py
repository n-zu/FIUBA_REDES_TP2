from args_client import args_client
from loguru import logger
import socket
import os
import sys

ENDIANESS = "little"
BYTES_READ = 1024
UPLOAD_SUCCESSFUL_HEADER = 3
ERROR_HEADER = 4
UNKNOWN_TYPE_ERROR = 0
FILE_NOT_FOUND_ERROR = 1


def upload(endianess, bytes_read):
    logger.remove()
    logger.add(sys.stdout, level='ERROR')

    args = args_client(True)

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
    FILEPATH = args.src
    FILENAME = args.name

    TYPE = (0).to_bytes(1, byteorder=endianess)

    logger.debug("getting file size")

    try:
        SIZE_INT = os.path.getsize(os.path.join(FILEPATH, FILENAME))
    except Exception:
        logger.error("no file found")
        return

    logger.debug("file size accessed successfully")

    SIZE = SIZE_INT.to_bytes(8, byteorder=endianess)
    logger.debug(f"file length: {str(SIZE_INT)}")

    FILENAME_BYTES = FILENAME.encode()

    FILENAME_LEN = len(FILENAME_BYTES).to_bytes(2, byteorder=endianess)
    logger.debug(f"filename length: {str(len(FILENAME_BYTES))}")

    ADDR = (HOST, int(PORT))

    logger.info("creating socket")
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    logger.info("conecting to server")
    client.connect(ADDR)

    logger.info("sending message")
    logger.debug("sending header")
    # send header
    client.send(TYPE)
    client.send(SIZE)
    client.send(FILENAME_LEN)
    client.send(FILENAME_BYTES)

    logger.debug("sending body")
    # send body
    with open(os.path.join(FILEPATH, FILENAME), "rb") as f:
        while file_bytes := f.read(bytes_read):
            client.send(file_bytes)

    logger.info("reading response")
    response_byte = client.recv(1)
    response = int.from_bytes(response_byte, byteorder=ENDIANESS)

    if response == UPLOAD_SUCCESSFUL_HEADER:
        logger.info("successfull upload")
    elif response == ERROR_HEADER:
        error_byte = client.recv(1)
        error = int.from_bytes(error_byte, byteorder=ENDIANESS)
        logger.error(f"server responeded with error {error}")

    logger.info("closing socket")
    client.close()


upload(ENDIANESS, BYTES_READ)