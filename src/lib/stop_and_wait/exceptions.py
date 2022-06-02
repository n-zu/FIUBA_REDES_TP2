class ProtocolError(Exception):
    def __init__(self, message='Protocol violation'):
        # Call the base class constructor with the parameters it needs
        super(ProtocolError, self).__init__(message)

class EndOfStream(Exception):
    pass