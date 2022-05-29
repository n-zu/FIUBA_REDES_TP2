from sys import byteorder
from args_client import args_client
from loguru import logger
import socket
import os
import sys

ENDIANESS = 'little'
BYTES_READ = 1024

def upload(endianess, bytes_read):
    args = args_client(True)

    logger.debug("arguments read")

    HOST = args.host
    PORT = args.port
    FILEPATH = args.src
    FILENAME = args.name
    
    #TODO: log levels

    TYPE = (0).to_bytes(1, byteorder=endianess)

    logger.debug("getting file size")

    try:
        SIZE_INT = os.path.getsize(FILEPATH + FILENAME)
    except:
        logger.error("no file found")
        return
    
    logger.debug("file size accessed successfully")

    SIZE = SIZE_INT.to_bytes(8, byteorder=endianess)

    FILENAME_BYTES = FILENAME.encode()

    ADDR = (HOST, PORT)

    logger.info("creating socket")
    #client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    logger.info("conecting to server")
    #client.connect(ADDR)

    logger.info("sending message")
    logger.debug("sending header")
    #send header
    #client.send(TYPE)
    #client.send(SIZE)
    #client.send(FILENAME_BYTES)

    logger.debug("sending body")
    #send body
    with open(FILEPATH + FILENAME, 'rb') as f:
        while bytes := f.read(bytes_read):
            #client.send(bytes)
            print(bytes)

    logger.info("closing socket")
    #client.close()

upload(ENDIANESS, BYTES_READ)