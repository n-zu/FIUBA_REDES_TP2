import logging
import math
import queue
import socket
import threading
from lib.mux_demux.stream import MuxDemuxStream
from lib.utils import MTByteStream

logger = logging.getLogger(__name__)

CONNACK_WAIT_TIMEOUT = 500

CONNECT = "0"
CONNACK = "1"
INFO = "2"
ACK = "3"

# No envie el CONNECT (si soy socket) ni lo recibi (si soy listener)
NOT_CONNECTED = "NOT_CONNECTED"
# Soy Socket de listener, mande el CONNACK y ya recibi info
# (confirma que el cliente recibio el CONNECT)
CONNECTING = "CONNECTING"
# Soy Socket de listener, y recibi el CONNECT
CONNECTED = "CONNECTED"


class Packet:
    def __init__(self):
        self.type = None
        self.headers = {}
        self.body = None

    def decode(self, data):
        raw_type = data[:1].decode("utf-8")
        if raw_type == CONNECT:
            self.type = CONNECT
            if len(data) > 1:
                logger.error("Connect packet has extra data, dropping")

        raise NotImplementedError

    @classmethod
    def connack(cls):
        packet = cls()
        packet.type = CONNACK
        return packet

    @classmethod
    def ack(cls):
        packet = cls()
        packet.type = ACK
        return packet

    @classmethod
    def read_from_stream(cls, stream):
        logger.debug("Reading packet from stream")
        packet = cls()
        packet_type_raw = stream.recv_exact(1)
        packet_type = packet_type_raw.decode("utf-8")
        if packet_type == CONNECT:
            if len(packet_type_raw) != 1:
                logger.error("Connect packet has extra data, dropping")
            packet.type = CONNECT
            return packet
        elif packet_type == CONNACK:
            if len(packet_type_raw) != 1:
                logger.error("Connack packet has extra data, dropping")
            packet.type = CONNACK
            return packet
        elif packet_type == INFO:
            packet.type = INFO
            packet.headers["length"] = int.from_bytes(
                stream.recv_exact(16), byteorder="big"
            )
            packet.headers["packet_number"] = int.from_bytes(
                stream.recv_exact(4), byteorder="big"
            )
            packet.body = stream.recv_exact(packet.headers["length"])
            return packet
        elif packet_type == ACK:
            if len(packet_type_raw) != 1:
                logger.error("ACK packet has extra data, dropping")
            packet.type = ACK
            return packet
        else:
            # Faltan FIN y FINACK
            # Aca habria que cerrar la conexion
            raise Exception("Unknown packet type (%s)" % packet_type)

    def encode(self):
        if self.type == CONNECT:
            return CONNECT.encode("utf-8")
        elif self.type == CONNACK:
            return CONNACK.encode("utf-8")
        elif self.type == INFO:
            packet_bytes = b""
            packet_bytes += self.type.encode("utf-8")
            packet_bytes += self.headers["length"].to_bytes(
                16, byteorder="big"
            )
            packet_bytes += self.headers["packet_number"].to_bytes(
                4, byteorder="big"
            )
            packet_bytes += self.body
            return packet_bytes
        elif self.type == ACK:
            return ACK.encode("utf-8")
        else:
            raise Exception("Unknown packet type")

    @classmethod
    def divide_buffer(cls, buffer, packet_size):
        packets = []
        for i in range(0, math.ceil(len(buffer) / packet_size)):
            packet = cls()
            packet.type = INFO
            packet.headers["length"] = packet_size
            packet.headers["packet_number"] = i
            packet.body = buffer[i * packet_size : (i + 1) * packet_size]
            packets.append(packet)

        return packets

    @classmethod
    def connect(cls):
        packet = cls()
        packet.type = CONNECT
        return packet


class SAWSocket:
    def __init__(self):
        self.socket = None
        self.packet_thread_handler = None
        self.expected_packet_number = 0

        self.is_from_listener = None
        self.status = NOT_CONNECTED

        self.ack_queue = queue.Queue()
        self.info_bytestream = None

    def from_listener(self, mux_demux_socket):
        self.is_from_listener = True
        self.socket = mux_demux_socket

        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.packet_thread_handler.start()
        self.info_bytestream = MTByteStream()

    def connect(self, addr):
        self.is_from_listener = False
        logger.debug(f"Connecting to {addr[0]}:{addr[1]}")
        self.socket = MuxDemuxStream()
        self.socket.connect(addr)
        # self.socket.setblocking(False)
        self.socket.settimeout(CONNACK_WAIT_TIMEOUT)
        while True:
            try:
                logger.debug("Sending connect packet")
                self.socket.send_all(Packet.connect().encode())
                logger.debug("Waiting for connack packet")
                packet = Packet.read_from_stream(self.socket)
                if packet.type == CONNACK:
                    self.status = CONNECTED
                    break
                else:
                    logger.error(
                        "Received unexpected packet type (expected CONNACK)"
                    )
            except socket.timeout:
                logger.debug("Time out waiting for CONNACK, sending again")
        logger.debug("Connected")
        self.packet_thread_handler = threading.Thread(
            target=self.packet_handler
        )
        self.packet_thread_handler.start()

    def packet_handler(self):
        logger.debug("Packet handler started")
        while True:
            packet = Packet.read_from_stream(self.socket)
            logger.debug(
                f"Received packet {packet.type} with headers {packet.headers} and body {packet.body}"
            )
            if packet.type == CONNECT:
                self.handle_connect(packet)
            elif packet.type == CONNACK:
                self.handle_connack(packet)
            elif packet.type == INFO:
                self.handle_info(packet)
            elif packet.type == ACK:
                self.handle_ack(packet)
            else:
                logger.error("Received unknown packet type")

    def handle_info(self, packet):
        if self.status == NOT_CONNECTED:
            # logger.error("Received INFO packet while not connected")
            raise Exception("Received INFO packet while not connected")
        elif self.status == CONNECTING:
            # Confirmo que ya se recibio el CONNACK
            self.status = CONNECTED

        if self.expected_packet_number == packet.headers["packet_number"]:
            logger.debug(
                "Received expected INFO packet (number %d)"
                % packet.headers["packet_number"]
            )
            self.socket.send_all(Packet.ack().encode())
            self.info_bytestream.put_bytes(packet.body)
            self.expected_packet_number += 1
        elif (
            packet.headers["packet_number"] == self.expected_packet_number - 1
        ):
            logger.debug("Received INFO retransmission")
            self.socket.send_all(Packet.ack().encode())
        else:
            logger.error(
                "Received unexpected INFO packet, dropping (expected %s, received %s)"
                % (
                    self.expected_packet_number,
                    packet.headers["packet_number"],
                )
            )
            raise Exception(
                "Received unexpected INFO packet, dropping (expected %s, received %s)"
                % (
                    self.expected_packet_number,
                    packet.headers["packet_number"],
                )
            )

    def handle_connect(self, packet):
        if self.is_from_listener:
            if self.status == NOT_CONNECTED or self.status == CONNECTING:
                self.status = CONNECTING
                self.socket.send_all(Packet.connack().encode())
            else:  # self.status == CONNECTED
                logger.error("Received connect packet while already connected")
        else:  # socket from client
            logger.error("Received connect packet from server")

    def handle_connack(self, packet):
        if self.is_from_listener:
            logger.error("Received connack packet being socket from listener")
        else:
            if self.status == CONNECTING:
                self.status = CONNECTED
                logger.debug("Connected")
            else:
                logger.error(
                    "Received connack packet while not connecting (status: %s)"
                    % self.status
                )

    def handle_ack(self, packet):
        if self.status != CONNECTED:
            logger.error("Receiving ACK packet while not connected")
        else:
            logger.debug("Receiving ACK packet")
            self.ack_queue.put(packet)

    def send(self, buffer):
        logger.debug(f"Sending buffer {buffer}")

        if self.status != CONNECTED:
            logger.error("Trying to send data while not connected")
        else:
            logger.debug("Sending data")
            packets = Packet.divide_buffer(buffer, 4)
            logger.debug("Fragmented buffer into %d packets" % len(packets))

            for packet in packets:
                logger.debug(
                    "Sending packet %d" % packet.headers["packet_number"]
                )
                while True:
                    self.socket.send_all(packet.encode())
                    try:
                        ack = self.ack_queue.get(timeout=15)
                        logger.debug("Received ACK packet")
                        break
                    except queue.Empty:
                        logger.error(
                            "Timeout waiting for ACK packet, sending again"
                        )

    def recv(self, buff_size):
        if self.status == NOT_CONNECTED:
            logger.error("Trying to receive data while not connected")
            raise Exception(
                f"Trying to receive data while not connected (status {self.status})"
            )
        else:
            logger.debug("Receiving data (buff_size %d)" % buff_size)
            info_body_bytes = self.info_bytestream.get_bytes(
                buff_size, timeout=1
            )
            if len(info_body_bytes) > 0:
                logger.debug(
                    "Received INFO packet (%d bytes)" % len(info_body_bytes)
                )
                return info_body_bytes
            else:
                return b""
