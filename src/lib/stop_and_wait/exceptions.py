class ProtocolViolation(Exception):
    def __init__(self, message='Protocol violation'):
        # Call the base class constructor with the parameters it needs
        super(ProtocolViolation, self).__init__(message)
