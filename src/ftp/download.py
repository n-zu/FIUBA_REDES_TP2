import os
from ftp.args_client import args_client
from lib.selective_repeat.sr_socket import SRSocket
from loguru import logger


ENDIANESS = "little"
BYTES_READ = 1024
CONFIRM_DOWNLOAD_HEADER = 2
ERROR_HEADER = 4
UNKNOWN_TYPE_ERROR = 0
FILE_NOT_FOUND_ERROR = 1


def download(endianess, bytes_read):
    args = args_client(False)

    logger.debug("arguments read")

    HOST = args.host
    PORT = args.port
    FILEPATH = args.dst
    FILENAME = args.name

    # TODO: log levels

    TYPE = (1).to_bytes(1, byteorder=endianess)

    FILENAME_BYTES = FILENAME.encode()

    FILENAME_LEN = len(FILENAME_BYTES).to_bytes(2, byteorder=endianess)
    logger.debug(f"filename length: {str(len(FILENAME_BYTES))}")

    ADDR = (HOST, int(PORT))

    logger.info("creating socket")
    client = SRSocket()

    logger.info("conecting to server")
    client.connect(ADDR)

    logger.info("sending message")
    logger.debug("sending header")
    # send header
    client.send(TYPE)
    client.send(FILENAME_LEN)
    client.send(FILENAME_BYTES)

    type_byte = client.recv(1)
    type = int.from_bytes(type_byte, byteorder=ENDIANESS)

    if type == ERROR_HEADER:
        error_byte = client.recv(1)
        error = int.from_bytes(error_byte, byteorder=ENDIANESS)
        if error == FILE_NOT_FOUND_ERROR:
            logger.error(f"the file {FILENAME} was not found in the server")
        else:
            logger.error("unknown error")
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
    counter = 0
    with open(os.path.join(FILEPATH, FILENAME), "wb") as file:
        while counter < file_size:
            data = client.recv(bytes_read)
            file.write(data)
            counter += len(data)
    logger.debug("body download finished")

    logger.info("closing socket")
    client.close()
    logger.debug("socket closed")


download(ENDIANESS, BYTES_READ)
