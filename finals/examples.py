import asyncio
from handshakes import HandShake
from converses import Converse


class HandShakeCaseProtocol(asyncio.StreamReaderProtocol):

    @staticmethod
    async def handshake_case(self):
        hs = HandShake(uri)
        res = await hs.handshake_()
        print(res)


# uri = 'ws://echo.websocket.org'
# host = 'echo.websocket.org'
# port = 80
uri = 'wss://echo.websocket.org'
host = 'echo.websocket.org'
port = 443
loop = asyncio.get_event_loop()


async def main():
    reader, writer = await asyncio.open_connection(host=host, port=port, ssl=True)
    hs = HandShake(uri, reader, writer)
    await hs.handshake_()
    res = await hs.handshake_result()
    cov = Converse(reader, writer)
    while res == 101:
        message = b'James'
        cov.send(message)
        asyncio.sleep(2)
        rec = cov.receive()
        print(rec)

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
