"""WebSocket Operation Code and Frame
    https://tools.ietf.org/html/rfc6455#section-5.5
"""

__all__ = ['SocketState', 'StatusCode', 'OperationCode', 'CtrlCode', 'CloseCode']

from enum import IntEnum


CloseCode = [1000, 1001, 1002, 1003, 1007, 1008, 1009, 1010, 1011]


class SocketState(IntEnum):
    zero, connecting, opened, closing, closed = (0, 0, 1, 2, 3)


class StatusCode(IntEnum):
    """ 状态码及含义 https://github.com/asyncins/asyncwsc """
    normal, going, protocol_error, not_status, abnormal, internal = (1000, 1001, 1002, 1005, 1006, 1011)


class OperationCode(IntEnum):
    cont, text, binary = (0x00, 0x01, 0x02)


class CtrlCode(IntEnum):
    close, ping, pong = (0x08, 0x09, 0x0A)