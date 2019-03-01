from .parts import CTRL_CODE
__all__ = ["UnverifiedError", "StatusCodeError", "UnKnownError",
           "PayloadError", "FrameError", "ConnectionClosed",
           "CLOSE_CODE"]


class UnverifiedError(Exception):
    """ Exception raised when unverified """


class StatusCodeError(Exception):
    """ Exception raised when unverified """


class UnKnownError(Exception):
    """ Exception raised when unverified """


class PayloadError(Exception):
    """ Exception raised when unverified """


class FrameError(Exception):
    """ Exception raised when unverified """


class ConnectionClosed(Exception):
    """
    Exception raised when trying to read or write on a closed connection.

    Provides the connection close code and reason in its ``code`` and
    ``reason`` attributes respectively.

    """

    def __init__(self, code, reason):
        self.code = code
        self.reason = reason
        message = "WebSocket connection is closed: "
        message += self.format_close(code, reason)
        super().__init__(message)

    @staticmethod
    def format_close(code, reason):
        """
        Display a human-readable version of the close code and reason.

        """
        if 3000 <= code < 4000:
            explanation = "registered"
        elif 4000 <= code < 5000:
            explanation = "private use"
        else:
            explanation = CLOSE_CODES.get(code, "unknown")
        result = "code = {} ({}), ".format(code, explanation)

        if reason:
            result += "reason = {}".format(reason)
        else:
            result += "no reason"

        return result


CLOSE_CODE = {
    1000: "OK",
    1001: "going away",
    1002: "protocol error",
    1003: "unsupported type",
    # 1004 is reserved
    1005: "no status code [internal]",
    1006: "connection closed abnormally [internal]",
    1007: "invalid data",
    1008: "policy violation",
    1009: "message too big",
    1010: "extension required",
    1011: "unexpected error",
    1015: "TLS failure [internal]",
}
