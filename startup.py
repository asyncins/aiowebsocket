import sys
import asyncio
from .handshakes import Headers


class StartUp:
    def __int__(self, uri, *args,
                maximum=sys.maxsize, ping_interval=30, ping_timeout=30,
                queue_max=100,  timeout=30, read_size=2**16,
                write_size=2**16, loop=None,
                extension=None, extra_headers=None, close_timeout=None,
                origin=None, compression='deflate',
                **kwargs):
        if not loop:
            loop = asyncio.get_event_loop()
        url = Headers.uri_washing(uri)
        if url.resource:
            kwargs.setdefault('ssl', True)
        elif kwargs.get('ssl'):
            raise ValueError('Use wss://example.com to enable TLS')

        protocol=AsyncWebSocketClientProtocol
        host, port = url.host, url.port
        self._url = url
        self._origin = origin
