import queue
import socket
import threading


class MTByteStream:
    def __init__(self):
        self.stream = queue.SimpleQueue()
        self.extra = b""
        self.lock = threading.Lock()

    def get_bytes(self, buff_size, timeout=None, block=True):
        with self.lock:
            data = self.extra[:buff_size]
            self.extra = self.extra[buff_size:]
            try:
                while len(data) < buff_size:
                    data += self.stream.get(block=block, timeout=timeout)

                self.extra += data[buff_size:]
                return data[:buff_size]
            except queue.Empty as e:
                if len(data) == 0:
                    raise socket.timeout from e
                return data

    def put_bytes(self, data):
        self.stream.put(data)

    def empty(self):
        with self.lock:
            return len(self.extra) == 0 and self.stream.empty()
