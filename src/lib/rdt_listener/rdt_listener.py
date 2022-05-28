from lib.mux_demux.mux_demux_listener import MuxDemuxListener
from lib.stop_and_wait.saw_socket import SAWSocket
from lib.selective_repeat.sr_socket import SRSocket

from loguru import logger

STOP_AND_WAIT = "stop_and_wait"
SELECTIVE_REPEAT = "selective_repeat"


class RDTListener:
    def __init__(self, rdt_method: str, buggyness_factor=0.0):
        self.rdt_method = rdt_method
        self.queue_size = 0
        self.recv_addr = None
        self.mux_demux_listener = MuxDemuxListener(buggyness_factor)

    def bind(self, recv_addr):
        logger.debug(f"bind({recv_addr})")

        self.recv_addr = recv_addr
        self.mux_demux_listener.bind(recv_addr)

    def listen(self, queue_size):
        self.mux_demux_listener.listen(queue_size)

    def accept(self):
        new_mux_demux_stream = self.mux_demux_listener.accept()
        if self.rdt_method == STOP_AND_WAIT:
            new_rdt_stream = SAWSocket()
        elif self.rdt_method == SELECTIVE_REPEAT:
            new_rdt_stream = SRSocket()
        else:
            raise NotImplementedError
        new_rdt_stream.from_listener(new_mux_demux_stream)

        return new_rdt_stream

    def close(self):
        self.mux_demux_listener.close()
