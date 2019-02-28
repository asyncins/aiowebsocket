import logging
import asyncio
import binascii
import random
from struct import pack, unpack
from asyncio import StreamReaderProtocol, StreamReader, Lock, Queue
from enum import IntEnum
from collections import OrderedDict, abc

from .freams import Frames
from .parts import CLOSE, TEXT, BINARY, CONT, PING, PONG
from .exceptions import *


class SocketState(IntEnum):
    connecting, opened, closing, closed = (0, 1, 2, 3)


class AsyncWebSocketStreamReaderProtocol(StreamReaderProtocol):
    def __init__(self, host, port, protocol_name, ping_interval,
                 ping_timeout, timeout, maximum, queue_max, write_size,
                 read_size, loop, *args):
        self.host = host
        self.port = port,
        self.protocol_name = protocol_name
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.timeout = timeout
        self.maximum = maximum
        self.queue_max = queue_max
        self.write_size = write_size
        self.read_size = read_size
        self.loop = loop
        self.state = SocketState.connecting
        self.reader = None
        self.writer = None
        self.path = None
        self.request_headers = None
        self.response_headers = None
        self.sub_protocol = None
        self.extensions = []
        self.close_code = None
        self.close_reason = ''
        self._drain_lock = Lock(loop=loop)

        stream_reader = StreamReader(limit=self.read_size // 2, loop=loop)
        super().__init__(stream_reader, self.client_connected, loop)

        self.connection_lost_waiter = asyncio.Future(loop=loop)
        self.messages = Queue()
        self.task_transporter = None
        self.task_eunuch = None  # 传话太监
        self.task_close = None

    def client_connected(self, reader, writer):
        """TCP连接建立成功后调用
        """
        self.reader = reader
        self.writer = writer

    async def connection_open(self):
        """当WebSocket打开握手完成时回调。
        进入数据传输阶段
        """
        self.state = SocketState.opened
        # 创建任务-接收传入WebSocket消息
        self.task_trans = asyncio.wait(self.transfer_data())
        # 创建任务-传话太监定期发送ping
        self.task_eunuch = asyncio.wait(self.keepalive_ping())
        # 创建任务-发起连接关闭
        self.task_close = asyncio.wait(self.close_connection())

    @property
    def local(self):
        """连接的本地地址
        """
        return self.writer.get_extra_info('sockname')

    @property
    def remote(self):
        """连接的远程地址
        """
        return self.writer.get_extra_info('peername')

    @property
    def open(self):
        """当连接可用时此属性为true
        """
        return self.state is SocketState.opend and not self.task_trans.done()

    @property
    def closed(self):
        """连接关闭后此属性为true
        """
        return self.state is SocketState.closed

    async def receive(self):
        while len(self.messages) <= 0:
            await self.transfer_data_task
        message = self.messages.popleft()
        return message

    async def send(self, data):
        """发送消息
        """
        await self.ensure_open()

        # Unfragmented message (first because str and bytes are iterable).

        if isinstance(data, str):
            await self.write_frame(True, TEXT, data.encode('utf-8'))

        elif isinstance(data, bytes):
            await self.write_frame(True, BINARY, data)

        # Fragmented message -- regular iterator.

        elif isinstance(data, abc.Iterable):
            iter_data = iter(data)

            # First fragment.
            try:
                data = next(iter_data)
            except StopIteration:
                return
            data_type = type(data)
            if isinstance(data, str):
                await self.write_frame(False, TEXT, data.encode('utf-8'))
                encode_data = True
            elif isinstance(data, bytes):
                await self.write_frame(False, BINARY, data)
                encode_data = False
            else:
                raise TypeError("data must be an iterable of bytes or str")

            # Other fragments.
            for data in iter_data:
                if type(data) != data_type:
                    # We're half-way through a fragmented message and we can't
                    # complete it. This makes the connection unusable.
                    self.fail_connection(1011)
                    raise TypeError("data contains inconsistent types")
                if encode_data:
                    data = data.encode('utf-8')
                await self.write_frame(False, CONT, data)

            # Final fragment.
            await self.write_frame(True, CONT, type(data)())

        # Fragmented message -- asynchronous iterator

        # To be implemented after dropping support for Python 3.4.

        else:
            raise TypeError("data must be bytes, str, or iterable")

    async def wait_closed(self):
        """
        Wait until the connection is closed.

        This is identical to :attr:`closed`, except it can be awaited.

        This can make it easier to handle connection termination, regardless
        of its cause, in tasks that interact with the WebSocket connection.

        """
        await asyncio.shield(self.connection_lost_waiter)

    async def close(self, code=1000, reason=''):
        """
        This coroutine performs the closing handshake.

        It waits for the other end to complete the handshake and for the TCP
        connection to terminate. As a consequence, there's no need to await
        :meth:`wait_closed`; :meth:`close` already does it.

        :meth:`close` is idempotent: it doesn't do anything once the
        connection is closed.

        It's safe to wrap this coroutine in :func:`~asyncio.ensure_future`
        since errors during connection termination aren't particularly useful.

        ``code`` must be an :class:`int` and ``reason`` a :class:`str`.

        """
        try:
            await asyncio.wait_for(
                self.write_close_frame(Frames.serialize_close(code, reason)),
                self.close_timeout,
                loop=self.loop,
            )
        except asyncio.TimeoutError:
            # If the close frame cannot be sent because the send buffers
            # are full, the closing handshake won't complete anyway.
            # Fail the connection to shut down faster.
            self.fail_connection()

        # If no close frame is received within the timeout, wait_for() cancels
        # the data transfer task and raises TimeoutError.

        # If close() is called multiple times concurrently and one of these
        # calls hits the timeout, the data transfer task will be cancelled.
        # Other calls will receive a CancelledError here.

        try:
            # If close() is canceled during the wait, self.transfer_data_task
            # is canceled before the timeout elapses (on Python ≥ 3.4.3).
            # This helps closing connections when shutting down a server.
            await asyncio.wait_for(
                self.transfer_data_task, self.close_timeout, loop=self.loop
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

        # Wait for the close connection task to close the TCP connection.
        await asyncio.shield(self.close_connection_task)

    async def ensure_open(self):
        """
        Check that the WebSocket connection is open.
        """
        # Handle cases from most common to least common for performance.
        if self.state is SocketState.opend:
            # If self.transfer_data_task exited without a closing handshake,
            # self.close_connection_task may be closing it, going straight
            # from OPEN to CLOSED.
            if self.transfer_data_task.done():
                await asyncio.shield(self.close_connection_task)
                raise ConnectionClosed(
                    self.close_code, self.close_reason
                ) from self.transfer_data_exc
            else:
                return

        if self.state is SocketState.closed:
            raise ConnectionClosed(
                self.close_code, self.close_reason
            ) from self.transfer_data_exc

        if self.state is SocketState.closing:
            # If we started the closing handshake, wait for its completion to
            # get the proper close code and status. self.close_connection_task
            # will complete within 4 or 5 * close_timeout after close(). The
            # CLOSING state also occurs when failing the connection. In that
            # case self.close_connection_task will complete even faster.
            if self.close_code is None:
                await asyncio.shield(self.close_connection_task)
            raise ConnectionClosed(
                self.close_code, self.close_reason
            ) from self.transfer_data_exc

        # Control may only reach this point in buggy third-party subclasses.
        assert self.state is SocketState.connecting
        raise ConnectionError("WebSocket connection isn't established yet")

    async def transfer_data(self):
        """读取消息并将其放入队列。
        """
        try:
            while True:
                message = await self.read_message()
                if message is None:  # 接收到闭合帧时退出循环。
                    break
                self.messages.append(message)
        except Exception as exc:
            logging.warning(exc)
            await self.connection_fail(code=1011)

    async def connection_fail(self, code=1006, reason=''):
        """ 连接失败,需要发起连接关闭操作。关闭时需要处理以下事项：
        * 停止所有数据的传入传出

        :param code:
        :param reason:
        :return:
        """
        if self.task_trans:
            self.task_trans.cancel()
        if code != 1006 and self.state is SocketState.opened:
            frame_data = Frames.serialize_close_frame(code, reason)
            self.state = SocketState.closing
            frame = Frames(True, CLOSE, frame_data)
            frame.write(self.writer.write, mask=self.is_client,
                        extensions=self.extensions)
        if not self.task_close:
            self.task_close = asyncio.wait(self.close_connection())

    async def wait_for_connection_lost(self):
        """等待TCP连接关闭或self.close_timeout。
        如果连接已关闭返回true,否则返回false
        """
        if not self.connection_lost_waiter.done():
            try:
                await asyncio.wait_for(
                    asyncio.shield(self.connection_lost_waiter),
                    self.close_timeout,
                    loop=self.loop,
                )
            except asyncio.TimeoutError:
                pass
        return self.connection_lost_waiter.done()

    def connection_made(self, transport):
        """配置缓冲区(写)限制,限值由self.write_size决定
        """
        transport.set_write_buffer_limits(self.write_size)
        super().connection_made(transport)

    def eof_received(self):
        """收到EOF时关闭transport
        """
        super().eof_received()
        return

    def connection_lost(self, exc):
        """连接关闭
        """
        self.state = SocketState.closed
        if not self.close_code:
            self.close_code = 1006
        self.abort_keepalive_pings()
        self.connection_lost_waiter.set_result(None)
        super().connection_lost(exc)

