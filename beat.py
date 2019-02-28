from struct import pack, unpack
import random
import asyncio
import logging
from collections import OrderedDict
from .parts import PING, PONG, message_washing

from .protocols import SocketState, AsyncWebSocketStreamReaderProtocol


class RespBeat:
    """太监与太监的传话
    * 在连接建立之后，随时都可以发送Ping帧
    * 当收到平公公Ping帧的时候,彭公公需要立即返回Pong帧
    * 两位公公互相传话是因为需要确认双方在线
    * 平公公说什么,彭公公必须回什么
    """

    def __int__(self, protocols, interval=30, timeout=30):
        self.interval = interval
        self.timeout = timeout
        self.queues = OrderedDict
        self.protocols = AsyncWebSocketStreamReaderProtocol()

    async def ping(self, mes=None):
        """传话太监平公公
        想说什么就说什么
        """
        if mes:
            message = message_washing(mes)

        # Protect against duplicates if a payload is explicitly set.
        if message in self.queues:
            raise ValueError("Already waiting for a pong with the same data")

        # Generate a unique random payload otherwise.
        if message is None or message in self.queues:
            message = pack('!I', random.getrandbits(32))

        await self.protocols.write_frame(True, PING, message)

    async def pong(self, mes=b''):
        """回话太监彭公公
        平公公说什么，彭公公必须回什么
        """
        message = message_washing(mes)
        await self.protocols.write_frame(True, PONG, message)

    async def keep_alive_ping(self):
        """平公公发出传话并等待彭公公回话
        """
        try:
            while True:
                await asyncio.sleep(self.interval, loop=self.loop)
                ping_waiter = await self.ping()
                await asyncio.wait_for(ping_waiter, self.timeout, loop=self.loop)
        except Exception as exc:
            logging.warning(exc)

    def abort_keep_alive_pings(self):
        """中止两位公公的传话
        """
        exc = ConnectionError(self.close_code, self.close_reason)
        exc.__cause__ = self.transfer_data_exc  # emulate raise ... from ...
        for p in self.queues.values():
            p.set_exception(exc)
