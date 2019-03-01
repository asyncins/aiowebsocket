import logging
import asyncio
import binascii
import random
from struct import pack, unpack
from asyncio import StreamReaderProtocol, StreamReader, Lock, Queue, StreamWriter
from enum import IntEnum
from collections import abc

from .freams import Frames
from .parts import CLOSE, TEXT, BINARY, CONT, PING, PONG
from .exceptions import *


class SocketState(IntEnum):
    zero, connecting, opened, closing, closed = (0, 0, 1, 2, 3)


class AsyncStreamReaderProtocol(StreamReaderProtocol):
    def __init__(self, host, port,
                 timeout, maximum, write_size,
                 read_size, loop, *args):
        self.host = host,
        self.port = port,
        self.timeout = timeout
        self.maximum = maximum
        self.state = SocketState.zero
        self.close_code = None
        self.task_trans = None
        self.task_eunuch = None
        self.task_close = None
        self.reader = StreamReader
        self.writer = StreamWriter
        self.extensions = []
        self._drain_lock = Lock()
        self.write_size = write_size
        self.read_size = read_size
        self.loop = loop if not loop else asyncio.get_event_loop()

        stream_reader = asyncio.StreamReader(limit=self.read_size // 2, loop=loop)
        super().__init__(stream_reader, self.client_connected, loop)

    def connection_made(self, transport):
        """设置缓冲区(写)限值"""
        transport.set_write_buffer_limits(self.write_size)
        super().connection_made(transport)

    async def connection_open(self):
        """当WebSocket打开握手完成时回调。
        进入数据传输阶段
        """
        self.state = SocketState.opened
        self.task_trans = asyncio.Task(self.transfer_data())  # 创建消息接收任务
        self.task_eunuch = asyncio.Task(self.keep_alive_ping())  # 创建传话太监
        self.task_close = asyncio.Task(self.close_connection())  # 创建关闭任务

    def connection_lost(self, exc):
        """当连接丢失或关闭时调用"""
        self.state = SocketState.closed
        if not self.close_code:
            self.close_code = 1006
        # 关闭前处理：在挂起的keep alive ping中引发connection closed。
        self.abort_keepalive_pings()
        super().connection_lost(exc)

    async def connection_fail(self, code=1006, reason='', ):
        """ 连接失败,需要发起连接关闭操作。关闭时需要处理以下事项：
        """
        if self.task_trans:  # 停止所有数据的传入传出
            self.task_trans.cancel()
        if code != 1006 and self.state is SocketState.opened:
            frame_data = Frames.serialize_close_frame(code, reason)
            self.state = SocketState.closing
            frame = Frames(True, CLOSE, frame_data)
            frame.write(self.writer.write, mask=self.is_client,
                        extensions=self.extensions)
        if not self.task_close:
            self.task_close = asyncio.wait(self.close_connection())

    # def data_received(self, data: bytes):
    #     pass

    def eof_received(self):
        """收到EOF时关闭传输"""
        return super().eof_received()

    @property
    def open(self):
        """连接是否已打开"""
        return self.state is SocketState.opend

    @property
    def closed(self):
        """连接是否已关闭"""
        return self.state is SocketState.closed

    async def receive(self):
        """ 从队列中取出一条信息 """
        while len(self.messages) <= 0:
            await self.task_trans
        message = self.messages.popleft()
        return message

    async def transfer_data(self):
        """读取消息并将其放入队列"""
        try:
            while True:
                message = await self.read_message()
                if message is None:  # 接收到闭合帧时退出循环。
                    break
                self.messages.append(message)
        except Exception as exc:
            logging.warning(exc)
            await self.connection_fail(code=1011)

    async def read_message(self):
        pass

