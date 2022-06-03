import os
from lib.ftp.args_client import args_client
from lib.selective_repeat.sr_socket import SRSocket
from lib.stop_and_wait.saw_socket import SAWSocket
from lib.rdt_listener.rdt_listener import SELECTIVE_REPEAT, STOP_AND_WAIT
from loguru import logger
import sys

ENDIANESS = "little"
BYTES_READ = 1024
CONFIRM_DOWNLOAD_HEADER = 2
ERROR_HEADER = 4
UNKNOWN_TYPE_ERROR = 0
FILE_NOT_FOUND_ERROR = 1
TYPE = b"\x01"


def download(
    host,
    port,
    filepath,
    filename,
    endianess,
    bytes_read,
    method=SELECTIVE_REPEAT,
):

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
    client.send(TYPE + FILENAME_LEN + FILENAME_BYTES)

    type_byte = client.recv(1)
    type = int.from_bytes(type_byte, byteorder=ENDIANESS)

    if type == ERROR_HEADER:
        error_byte = client.recv(1)
        error = int.from_bytes(error_byte, byteorder=ENDIANESS)
        if error == FILE_NOT_FOUND_ERROR:
            logger.error(f"the file {filename} was not found in the server")
        else:
            logger.error("unknown error")
        logger.debug("closing socket")
        client.close()
        logger.error("exiting")
        return

    if type != CONFIRM_DOWNLOAD_HEADER:
        logger.error("wrong packet type")
        return

    logger.debug("reading file length")
    file_size_bytes = client.recv(8)

    file_size = int.from_bytes(file_size_bytes, byteorder=endianess)
    logger.debug(f"file size: {str(file_size)}")

    logger.debug("downloading body")

    if not os.path.exists(filepath):
        os.makedirs(filepath)

    counter = 0
    with open(os.path.join(filepath, filename), "wb") as file:
        while counter < file_size:
            data = client.recv(bytes_read)
            file.write(data)
            counter += len(data)
    logger.debug("body download finished")

    logger.info("closing socket")
    client.close()
    logger.debug("socket closed")


if __name__ == "__main__":
    args = args_client(False)

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
    FILEPATH = args.dst
    FILENAME = args.name
    download(HOST, PORT, FILEPATH, FILENAME, ENDIANESS, BYTES_READ)
