import os
from lib.ftp.args_client import args_client
from lib.selective_repeat.sr_socket import SRSocket
from lib.rdt_listener.rdt_listener import SELECTIVE_REPEAT, STOP_AND_WAIT
from lib.stop_and_wait.saw_socket import SAWSocket
from loguru import logger
import sys
import time

ENDIANESS = "little"
BYTES_READ = 60000
UPLOAD_SUCCESSFUL_HEADER = 3
ERROR_HEADER = 4
UNKNOWN_TYPE_ERROR = 0
FILE_NOT_FOUND_ERROR = 1
TYPE = b"\x00"


def upload(
    host,
    port,
    filepath,
    filename,
    endianess,
    bytes_read,
    method=SELECTIVE_REPEAT,
):
    logger.debug("arguments read")

    logger.debug("getting file size")

    try:
        SIZE_INT = os.path.getsize(os.path.join(filepath, filename))
    except Exception:
        logger.error("no file found")
        return

    logger.debug("file size accessed successfully")

    SIZE = SIZE_INT.to_bytes(8, byteorder=endianess)
    logger.debug(f"file length: {str(SIZE_INT)}")

    FILENAME_BYTES = filename.encode()

    FILENAME_LEN = len(FILENAME_BYTES).to_bytes(2, byteorder=endianess)
    logger.debug(f"filename length: {str(len(FILENAME_BYTES))}")

    ADDR = (host, int(port))

    logger.info("creating socket")
    if method == SELECTIVE_REPEAT:
        client = SRSocket()
    elif method == STOP_AND_WAIT:
        client = SAWSocket()
    else:
        raise Exception("Invalid transport method")

    logger.info("conecting to server")
    client.connect(ADDR)

    logger.info("sending message")
    logger.debug("sending header")
    # send header
    client.send(TYPE + SIZE + FILENAME_LEN + FILENAME_BYTES)

    logger.debug("sending body")
    # send body
    with open(os.path.join(filepath, filename), "rb") as f:
        while file_bytes := f.read(bytes_read):
            client.send(file_bytes)

    logger.info("reading response")
    response_byte = client.recv(1)
    response = int.from_bytes(response_byte, byteorder=endianess)

    if response == UPLOAD_SUCCESSFUL_HEADER:
        logger.info("successfull upload")
    elif response == ERROR_HEADER:
        error_byte = client.recv(1)
        error = int.from_bytes(error_byte, byteorder=endianess)
        logger.error(f"server responeded with error {error}")

    logger.info("closing socket")
    client.close()


if __name__ == "__main__":
    args = args_client(True)

    logger.remove()
    if args.quiet:
        logger.add(sys.stdout, level="ERROR")
    elif args.verbose:
        logger.add(sys.stdout, level="DEBUG")
        logger.debug("in verbose mode")
    else:
        logger.add(sys.stdout, level="INFO")

    HOST = args.host
    PORT = args.port
    FILEPATH = args.src
    FILENAME = args.name

    start = time.time()
    upload(
        HOST,
        PORT,
        FILEPATH,
        FILENAME,
        ENDIANESS,
        BYTES_READ,
        method="selective_repeat",
    )
    stop = time.time()
    logger.info(f"Upload time: {stop - start}")
