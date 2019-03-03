import asyncio
from converses import Connect
from datetime import datetime
from random import randint


async def startup(uri):
    async with Connect(uri) as connect:
        converse = connect.manipulator
        for _ in range(6):
            message = b'Async WebSocket Client'
            await converse.send(message)
            print('{i} - send message: {m}'.format(i=_, m=message))

        # mes = await converse.receive()
        # print('size: %s' % converse.get_queue_size)
        # tn = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # print('{_} - {tn} - - Client receive: {rec}'.format(_=_, tn=tn, rec=mes))

        while True:
            mes = await converse.receive()
            tn = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print('{tn} - - Client receive: {rec}'.format(tn=tn, rec=mes))


if __name__ == '__main__':
    uri = 'ws://echo.websocket.org'
    asyncio.get_event_loop().run_until_complete(startup(uri))
