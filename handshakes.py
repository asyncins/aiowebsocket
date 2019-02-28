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
