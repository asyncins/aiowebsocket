from enum import IntEnum


__all__ = ['SocketState', 'DataFrames', 'ControlFrames', 'StatusCodes']


# When closing an established connection (e.g., when sending a Close
# frame, after the opening handshake has completed), an endpoint MAY
# indicate a reason for closure.  The interpretation of this reason by
# an endpoint, and the action an endpoint should take given this
# reason, are left undefined by this specification.  This specification
# defines a set of pre-defined status codes and specifies which ranges
# may be used by extensions, frameworks, and end applications.  The
# status code and any associated textual message are optional
# components of a Close frame.
# https://tools.ietf.org/html/rfc6455#section-7.4

StatusCodes = [1000, 1001, 1002, 1003, 1007, 1008, 1009, 1010, 1011]


class SocketState(IntEnum):
    """WebSocket connection state """
    zero, connecting, opened, closing, closed = (0, 0, 1, 2, 3)


class DataFrames(IntEnum):
    """Data frames (e.g., non-control frames) are identified by opcodes
    where the most significant bit of the opcode is 0.  Currently defined
    opcodes for data frames include 0x1 (Text), 0x2 (Binary).  Opcodes
    0x3-0x7 are reserved for further non-control frames yet to be

    https://tools.ietf.org/html/rfc6455#section-5.6
    """
    cont, text, binary = (0x00, 0x01, 0x02)


class ControlFrames(IntEnum):
    """Control frames are identified by opcodes where the most significant
    bit of the opcode is 1.  Currently defined opcodes for control frames
    include 0x8 (Close), 0x9 (Ping), and 0xA (Pong).  Opcodes 0xB-0xF are
    reserved for further control frames yet to be defined.

    Control frames are used to communicate state about the WebSocket.
    Control frames can be interjected in the middle of a fragmented
    message.

    All control frames MUST have a payload length of 125 bytes or less
    and MUST NOT be fragmented.

    https://tools.ietf.org/html/rfc6455#section-5.5
    """
    close, ping, pong = (0x08, 0x09, 0x0A)
