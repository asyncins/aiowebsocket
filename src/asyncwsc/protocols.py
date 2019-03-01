import logging
import asyncio
from asyncio import StreamReaderProtocol, StreamReader, Lock, StreamWriter
from . import messages_queue
from .freams import Frames
from .exceptions import *
from .enumerations import *
from .parts import character_convert


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
        self.messages_queue = messages_queue
        self.extensions = []
        self._drain_lock = Lock()
        self.write_size = write_size
        self.read_size = read_size
        self.frames = Frames()
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
            self.close_code = StatusCode.abnormal
        # 关闭前处理：在挂起的keep alive ping中引发connection closed。
        self.abort_keepalive_pings()
        super().connection_lost(exc)

    async def connection_fail(self, code=StatusCode.abnormal, reason=''):
        """ 连接失败,需要发起连接关闭操作。关闭时需要处理以下事项：
        """
        if self.task_trans:  # 如果有消息接收任务则需要先取消
            self.task_trans.cancel()
        if code is not StatusCode.abnormal and self.state is SocketState.opened:
            code, message = self.frames.serialize_close_frame(code, reason)
            self.state = SocketState.closing
            self.frames.write(fin=True, code=code, message=message)
        if not self.task_close:  # 如果没有连接关闭的任务，则创建用于关闭连接的任务
            await self.close_connection()
            # self.task_close = asyncio.Task(self.close_connection())

    async def close_connection(self) -> None:
        """当握手成功后需要等待传输完成后关闭TCP
        握手成功前或握手失败则意味着没有传输，不需要等待
        """
        if self.task_trans:  # 如果有消息接收任务则需要先取消
            self.task_trans.cancel()

        if self.task_eunuch:  # 撤回传话太监
            self.task_eunuch.cancel()

        if self.writer.can_write_eof():  # 刷新缓冲的写入数据后，停止流的写入。
            self.writer.write_eof()

        # 关闭写入与传输
        self.writer.close()
        self.writer.transport.abort()

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
        while len(self.messages_queue) <= 0:
            await self.task_trans
        message = self.messages_queue.get()
        return message

    async def transfer_data(self):
        """读取消息并将其放入队列"""
        try:
            while True:
                message = await self.read_message()
                if message is None:  # 接收到闭合帧时退出循环。
                    break
                self.messages_queue.append(message)
        except Exception as exc:
            logging.warning(exc)
            await self.connection_fail(code=StatusCode.internal)

    async def read_message(self):
        """从连接中读取单个消息。
        如果消息是分段的，则重新组装数据帧。
        结束握手开始时返回None"""
        frame = await self.read_frame(max_size=self.max_size)
        if not frame:
            return None
        if frame.code == OperationCode.text.value:
            text = True
        elif frame.code == OperationCode.binary.value:
            text = False
        else:
            raise ProtocolError("Unexpected OperationCode")
        if frame.fin:
            return frame.data.decode("utf-8") if text else frame.data


class ClientProtocol(AsyncStreamReaderProtocol):
    """  """
    def __init__(self):
        self.writer = StreamWriter

    def construct_header(self, resource: str = '/', header: bytes = b''):
        if header:
            header = character_convert(header)
        else:
            header = b"GET {resource} HTTP/1.1\r\n".format(resource=resource)
        self.writer.write(header)
