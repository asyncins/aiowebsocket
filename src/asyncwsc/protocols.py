import re
import logging
import asyncio
from asyncio import StreamReaderProtocol, StreamReader, Lock, StreamWriter
from . import messages_queue
from .freams import Frames
from .exceptions import *
from .enumerations import *
from .parts import character_convert
from .http import Headers


MAX_HEADERS = 256
MAX_LINE = 4096
_value_re = re.compile(rb"[\x09\x20-\x7e\x80-\xff]*")


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

    async def read_response(self, stream=StreamReader):
        """ 从返回信息中提取状态码及header信息 """
        result = await stream.readline()[:-2]
        pron, socket_code, reason = result.split(b'', 2)
        if pron != b"HTTP/1.1":
            raise ProtocolError("Unsupported HTTP version: %r" % pron)
        socket_code = int(socket_code)
        if not 100 <= socket_code < 1000:
            raise UnverifiedError("Unsupported HTTP status code: %d" % socket_code)
        if not _value_re.fullmatch(reason):
            raise UnverifiedError("Invalid HTTP reason phrase: %r" % reason)
        headers = await self.read_header(stream)
        return socket_code, reason.decode(), headers

    @staticmethod
    async def read_header(stream):
        """ https://tools.ietf.org/html/rfc7230#section-3.2 """
        _token_re = re.compile(rb"[-!#$%&\'*+.^_`|~0-9a-zA-Z]+")

        headers = Headers()
        for _ in range(MAX_HEADERS + 1):
            line = await stream.readline()[:-2]
            if line == b"":
                break

            # This may raise "ValueError: not enough values to unpack"
            raw_name, raw_value = line.split(b":", 1)
            if not _token_re.fullmatch(raw_name):
                raise ValueError("Invalid HTTP header name: %r" % raw_name)
            raw_value = raw_value.strip(b" \t")
            if not _value_re.fullmatch(raw_value):
                raise ValueError("Invalid HTTP header value: %r" % raw_value)
            name = raw_name.decode("ascii")  # guaranteed to be ASCII at this point
            value = raw_value.decode("ascii", "surrogateescape")
            headers[name] = value
        else:
            raise ValueError("Too many HTTP headers")
        return headers


    @staticmethod
    def process_extensions(
        headers: Headers,
        available_extensions: Optional[Sequence[ClientExtensionFactory]],
    ) -> List[Extension]:
        """
        Handle the Sec-WebSocket-Extensions HTTP response header.

        Check that each extension is supported, as well as its parameters.

        Return the list of accepted extensions.

        Raise :exc:`~websockets.exceptions.InvalidHandshake` to abort the
        connection.

        :rfc:`6455` leaves the rules up to the specification of each
        :extension.

        To provide this level of flexibility, for each extension accepted by
        the server, we check for a match with each extension available in the
        client configuration. If no match is found, an exception is raised.

        If several variants of the same extension are accepted by the server,
        it may be configured severel times, which won't make sense in general.
        Extensions must implement their own requirements. For this purpose,
        the list of previously accepted extensions is provided.

        Other requirements, for example related to mandatory extensions or the
        order of extensions, may be implemented by overriding this method.

        """
        accepted_extensions: List[Extension] = []

        header_values = headers.get_all("Sec-WebSocket-Extensions")

        if header_values:

            if available_extensions is None:
                raise InvalidHandshake("No extensions supported")

            parsed_header_values: List[ExtensionHeader] = sum(
                [parse_extension(header_value) for header_value in header_values], []
            )

            for name, response_params in parsed_header_values:

                for extension_factory in available_extensions:

                    # Skip non-matching extensions based on their name.
                    if extension_factory.name != name:
                        continue

                    # Skip non-matching extensions based on their params.
                    try:
                        extension = extension_factory.process_response_params(
                            response_params, accepted_extensions
                        )
                    except NegotiationError:
                        continue

                    # Add matching extension to the final list.
                    accepted_extensions.append(extension)

                    # Break out of the loop once we have a match.
                    break

                # If we didn't break from the loop, no extension in our list
                # matched what the server sent. Fail the connection.
                else:
                    raise NegotiationError(
                        f"Unsupported extension: "
                        f"name = {name}, params = {response_params}"
                    )

        return accepted_extensions

    @staticmethod
    def process_subprotocol(
        headers: Headers, available_subprotocols: Optional[Sequence[Subprotocol]]
    ) -> Optional[Subprotocol]:
        """
        Handle the Sec-WebSocket-Protocol HTTP response header.

        Check that it contains exactly one supported subprotocol.

        Return the selected subprotocol.

        """
        subprotocol: Optional[Subprotocol] = None

        header_values = headers.get_all("Sec-WebSocket-Protocol")

        if header_values:

            if available_subprotocols is None:
                raise InvalidHandshake("No subprotocols supported")

            parsed_header_values: Sequence[Subprotocol] = sum(
                [parse_subprotocol(header_value) for header_value in header_values], []
            )

            if len(parsed_header_values) > 1:
                subprotocols = ", ".join(parsed_header_values)
                raise InvalidHandshake(f"Multiple subprotocols: {subprotocols}")

            subprotocol = parsed_header_values[0]

            if subprotocol not in available_subprotocols:
                raise NegotiationError(f"Unsupported subprotocol: {subprotocol}")

        return subprotocol

    async def handshake(
        self,
        wsuri: WebSocketURI,
        origin: Optional[Origin] = None,
        available_extensions: Optional[Sequence[ClientExtensionFactory]] = None,
        available_subprotocols: Optional[Sequence[Subprotocol]] = None,
        extra_headers: Optional[HeadersLike] = None,
    ) -> None:
        """
        Perform the client side of the opening handshake.

        If provided, ``origin`` sets the Origin HTTP header.

        If provided, ``available_extensions`` is a list of supported
        extensions in the order in which they should be used.

        If provided, ``available_subprotocols`` is a list of supported
        subprotocols in order of decreasing preference.

        If provided, ``extra_headers`` sets additional HTTP request headers.
        It must be a :class:`~websockets.http.Headers` instance, a
        :class:`~collections.abc.Mapping`, or an iterable of ``(name, value)``
        pairs.

        Raise :exc:`~websockets.exceptions.InvalidHandshake` if the handshake
        fails.

        """
        request_headers = Headers()

        if wsuri.port == (443 if wsuri.secure else 80):  # pragma: no cover
            request_headers["Host"] = wsuri.host
        else:
            request_headers["Host"] = f"{wsuri.host}:{wsuri.port}"

        if wsuri.user_info:
            request_headers["Authorization"] = build_basic_auth(*wsuri.user_info)

        if origin is not None:
            request_headers["Origin"] = origin

        key = build_request(request_headers)

        if available_extensions is not None:
            extensions_header = build_extension(
                [
                    (extension_factory.name, extension_factory.get_request_params())
                    for extension_factory in available_extensions
                ]
            )
            request_headers["Sec-WebSocket-Extensions"] = extensions_header

        if available_subprotocols is not None:
            protocol_header = build_subprotocol(available_subprotocols)
            request_headers["Sec-WebSocket-Protocol"] = protocol_header

        if extra_headers is not None:
            if isinstance(extra_headers, Headers):
                extra_headers = extra_headers.raw_items()
            elif isinstance(extra_headers, collections.abc.Mapping):
                extra_headers = extra_headers.items()
            for name, value in extra_headers:
                request_headers[name] = value

        request_headers.setdefault("User-Agent", USER_AGENT)

        self.write_http_request(wsuri.resource_name, request_headers)

        status_code, response_headers = await self.read_http_response()
        if status_code in (301, 302, 303, 307, 308):
            if "Location" not in response_headers:
                raise UnverifiedError("Redirect response missing Location")
            raise ValueError(response_headers["Location"])
        elif status_code != 101:
            raise ValueError(status_code)

        check_response(response_headers, key)

        self.extensions = self.process_extensions(
            response_headers, available_extensions
        )

        self.subprotocol = self.process_subprotocol(
            response_headers, available_subprotocols
        )

        self.connection_open()
