import asyncio
from converses import Connect
from datetime import datetime


async def startup(uri):
    async with Connect(uri) as connect:
        converse = connect.manipulator
        message = b'Async WebSocket Client'
        while True:
            await converse.send(message)
            print('{time}-Client send: {message}'
                  .format(time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), message=message))
            mes = await converse.receive()
            print('{time}-Client receive: {rec}'
                  .format(time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), rec=mes))


if __name__ == '__main__':
    remote = 'ws://echo.websocket.org'
    asyncio.get_event_loop().run_until_complete(startup(remote))
