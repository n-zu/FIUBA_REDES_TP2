from sys import byteorder
from args_client import args_client
from loguru import logger
import socket
import os
import sys

ENDIANESS = 'little'
BYTES_READ = 1024
CONFIRM_DOWNLOAD_HEADER = 2

def download(endianess, bytes_read):
    args = args_client(False)

    logger.debug("arguments read")

    HOST = args.host
    PORT = args.port
    FILEPATH = args.dst
    FILENAME = args.name
    
    #TODO: log levels

    TYPE = (1).to_bytes(1, byteorder=endianess)

    FILENAME_BYTES = FILENAME.encode()

    FILENAME_LEN = len(FILENAME_BYTES).to_bytes(2, byteorder=endianess)
    print("FILENAME LENGTH: " + str(len(FILENAME_BYTES)))

    ADDR = (HOST, int(PORT))

    logger.info("creating socket")
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    logger.info("conecting to server")
    client.connect(ADDR)

    logger.info("sending message")
    logger.debug("sending header")
    #send header
    client.send(TYPE)
    client.send(FILENAME_LEN)
    client.send(FILENAME_BYTES)

    type_byte = client.recv(1)
    type = int.from_bytes(type_byte, byteorder=ENDIANESS)
    if type != CONFIRM_DOWNLOAD_HEADER:
        logger.error("wrong packet type")
        return

    logger.debug("reading file length")
    file_size_bytes = client.recv(8)

    file_size = int.from_bytes(file_size_bytes, byteorder=endianess)
    print("LENGTH: " + str(file_size))

    logger.debug("downloading body")
    counter = 0
    with open(os.path.join(FILEPATH, FILENAME), "wb") as file:
        while counter < file_size:
            data = client.recv(bytes_read)
            file.write(data)
            print(data.decode())
            counter += len(data)
    logger.debug("body download finished")

    logger.info("closing socket")
    client.close()
    logger.debug("socket closed")

download(ENDIANESS, BYTES_READ)