import asyncio
from .protocols import AsyncStreamReaderProtocol
from .handshakes import Headers

class Connect:
    max_redirects_allowed = 10

    def __init__(self, uri, interval=20, timeout=15,
                 size=2**16, headers=[], loop=None,
                 *args, **kwargs):
        self.timeout = timeout
        self.close_timeout = timeout
        self.protocol = AsyncStreamReaderProtocol
        self.loop = loop if loop else asyncio.get_event_loop()
        self.url = Headers.uri_washing(uri)
        if self.url.pron:
            kwargs.setdefault("ssl", True)

    async def _create_connect(self):
        factory = lambda: self.protocol(

        )
