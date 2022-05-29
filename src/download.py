from sys import byteorder
from args_client import args_client
from loguru import logger
import socket
import os
import sys

ENDIANESS = 'little'
BYTES_READ = 1024

def download(endianess, bytes_read):
    args = args_client(True)

    logger.debug("arguments read")

    HOST = args.host
    PORT = args.port
    FILEPATH = args.dst
    FILENAME = args.name
    
    #TODO: log levels

    TYPE = (1).to_bytes(1, byteorder=endianess)

    FILENAME_BYTES = FILENAME.encode()

    FILENAME_LEN = len(FILENAME_BYTES).to_bytes(2, byteorder=endianess)
    
    ADDR = (HOST, PORT)

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

    type = client.recv(1)
    if type != 3:
        logger.error("wrong packet type")
        return

    logger.debug("reading file length")
    file_size_bytes = client.recv(8)

    file_size = int.from_bytes(file_size_bytes, byteorder=endianess)

    logger.debug("downloading body")
    with open(FILEPATH + FILENAME, 'wb') as f:
        f.write(bytes([10]))
        bytes_count = file_size % bytes_read
        body = client.recv(bytes_count)
        f.write(body)
        while bytes_count < file_size:
            body = client.recv(bytes_read)
            f.write(body)
            bytes_count += bytes_read
    logger.debug("body download finished")

    logger.info("closing socket")
    client.close()
    logger.debug("socket closed")

download(ENDIANESS, BYTES_READ)