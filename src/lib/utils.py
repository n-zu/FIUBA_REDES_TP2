import queue


class MTByteStream:
    def __init__(self):
        self.buffer = b""
        self.stream = queue.SimpleQueue()

    def get_bytes(self, buff_size, timeout=None):
        data = b""
        try:
            while len(data) < buff_size:
                data += self.stream.get(block=True, timeout=timeout)
            return data
        except queue.Empty:
            return data

    def put_bytes(self, data):
        for byte_to_put in data:
            self.stream.put(byte_to_put.to_bytes(1, "big"))
