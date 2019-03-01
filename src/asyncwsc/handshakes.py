from urllib.parse import urlparse
from collections import namedtuple
from .exceptions import UnverifiedError


WebSocketURI = namedtuple('WebSocketURI', ['porn', 'host', 'port', 'resource', 'users'])


class Headers:
    def __int__(self):
        pass

    @staticmethod
    def uri_washing(uri):
        """Parse and validates the uri
        :param uri: a WebSocket URI,like:'ws://exam.com'
        :return:class-> WebSocketURI
        :raise: exceptions.Unverified
        """
        uri = urlparse(uri)
        try:
            porn = uri.scheme  # protocol name
            host = uri.hostname
            port = uri.port or (443 if porn == 'wss' else 80)
            users = None
            resource = uri.path or '/'
            if uri.query:
                resource += '?' + uri.query
            if uri.username or uri.password:
                users = (uri.username, uri.password)
        except AssertionError as exc:
            raise UnverifiedError("The '{uri}' unverified".format(uri=uri)) from exc
        return WebSocketURI(porn, host, port, resource, users)


def parse_list(
    parse_item: Callable[[str, int, str], Tuple[T, int]],
    header: str,
    pos: int,
    header_name: str,
) -> List[T]:
    """
    Parse a comma-separated list from ``header`` at the given position.

    This is appropriate for parsing values with the following grammar:

        1#item

    ``parse_item`` parses one item.

    ``header`` is assumed not to start or end with whitespace.

    (This function is designed for parsing an entire header value and
    :func:`~websockets.http.read_headers` strips whitespace from values.)

    Return a list of items.

    Raise :exc:`~websockets.exceptions.InvalidHeaderFormat` on invalid inputs.

    """
    # Per https://tools.ietf.org/html/rfc7230#section-7, "a recipient MUST
    # parse and ignore a reasonable number of empty list elements"; hence
    # while loops that remove extra delimiters.

    # Remove extra delimiters before the first item.
    while peek_ahead(header, pos) == ",":
        pos = parse_OWS(header, pos + 1)

    items = []
    while True:
        # Loop invariant: a item starts at pos in header.
        item, pos = parse_item(header, pos, header_name)
        items.append(item)
        pos = parse_OWS(header, pos)

        # We may have reached the end of the header.
        if pos == len(header):
            break

        # There must be a delimiter after each element except the last one.
        if peek_ahead(header, pos) == ",":
            pos = parse_OWS(header, pos + 1)
        else:
            raise InvalidHeaderFormat(header_name, "expected comma", header, pos)

        # Remove extra delimiters before the next item.
        while peek_ahead(header, pos) == ",":
            pos = parse_OWS(header, pos + 1)

        # We may have reached the end of the header.
        if pos == len(header):
            break

    # Since we only advance in the header by one character with peek_ahead()
    # or with the end position of a regex match, we can't overshoot the end.
    assert pos == len(header)

    return items


def parse_connection(header: str) -> List[ConnectionOption]:
    """
    Parse a ``Connection`` header.

    Return a list of connection options.

    Raise :exc:`~websockets.exceptions.InvalidHeaderFormat` on invalid inputs.

    """
    return parse_list(parse_connection_option, header, 0, "Connection")


def check_response(headers: Headers, key: str) -> None:
    """
    Check a handshake response received from the server.

    ``key`` comes from :func:`build_request`.

    If the handshake is valid, this function returns ``None``.

    Otherwise it raises an :exc:`~websockets.exceptions.InvalidHandshake`
    exception.

    This function doesn't verify that the response is an HTTP/1.1 or higher
    response with a 101 status code. These controls are the responsibility of
    the caller.

    """
    connection = sum(
        [parse_connection(value) for value in headers.get_all("Connection")], []
    )

    if not any(value.lower() == "upgrade" for value in connection):
        raise InvalidUpgrade("Connection", " ".join(connection))

    upgrade = sum([parse_upgrade(value) for value in headers.get_all("Upgrade")], [])

    # For compatibility with non-strict implementations, ignore case when
    # checking the Upgrade header. It's supposed to be 'WebSocket'.
    if not (len(upgrade) == 1 and upgrade[0].lower() == "websocket"):
        raise InvalidUpgrade("Upgrade", ", ".join(upgrade))

    try:
        s_w_accept = headers["Sec-WebSocket-Accept"]
    except KeyError:
        raise InvalidHeader("Sec-WebSocket-Accept")
    except MultipleValuesError:
        raise InvalidHeader(
            "Sec-WebSocket-Accept", "more than one Sec-WebSocket-Accept header found"
        )

    if s_w_accept != accept(key):
        raise InvalidHeaderValue("Sec-WebSocket-Accept", s_w_accept)
