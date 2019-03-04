import asyncio
import logging
from asyncio import Queue

from .freams import Frames
from .enumerations import SocketState, ControlFrames, DataFrames
from .handshakes import HandShake
from .parts import remote_url


class AioWebSocket:
    """Responsible for managing the
    connection between client and server
    """

    def __init__(self, uri: str, timeout: int = 20,
                 read_timeout: int = 120, ssl=False,
                 headers: list = []):
        self.uri = uri
        self.ssl = ssl
        self.hands = None
        self.reader = None
        self.writer = None
        self.converse = None
        self.timeout = timeout
        self.read_timeout = read_timeout
        self.headers = headers
        self.state = SocketState.zero.value

    async def close_connection(self):
        """Close connection.
        Check connection status before closing.
        Send Closed Frame to Server.
        """
        if self.state is SocketState.closed.value:
            raise ConnectionError('SocketState is closed, can not close.')
        if self.state is SocketState.closing:
            logging.warning('SocketState is closing')
        await self.converse.send(message=b'', code=ControlFrames.close.value)

    async def create_connection(self):
        """Create connection.
        Check the current connection status.
        Send out a handshake and check the result。
        """
        if self.state is not SocketState.zero.value:
            raise ConnectionError('Connection is already exists.')
        remote = porn, host, port, resource, users = remote_url(self.uri)
        reader, writer = await asyncio.open_connection(host=host, port=port, ssl=self.ssl)
        self.reader = reader
        self.writer = writer
        self.hands = HandShake(remote, reader, writer, headers=self.headers)
        await self.hands.shake_()
        status_code = await self.hands.shake_result()
        if status_code is not 101:
            raise ConnectionError('Connection failed,status code:{code}'.format(code=status_code))
        self.converse = Converse(reader, writer)
        self.state = SocketState.opened.value

    @property
    def manipulator(self):
        return self.converse

    async def __aenter__(self):
        create = asyncio.wait_for(self.create_connection(), timeout=self.timeout)
        try:
            await create
        except asyncio.TimeoutError as exc:
            raise ConnectionError('Connection time out,exc:{exc}'.format(exc=exc))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_connection()


class Converse:
    """Responsible for communication
    between client and server
    """
    def __init__(self, reader: object, writer: object, maxsize: int = 2**16):
        self.reader = reader
        self.writer = writer
        self.message_queue = Queue(maxsize=maxsize)
        self.frame = Frames(self.reader, self.writer)

    async def send(self, message: bytes, fin: bool = True,
                   code: int = DataFrames.binary.value):
        """Send message to server """
        if isinstance(message, str):
            message = message.encode('utf-8')
        if isinstance(message, bytes):
            message = message
        else:
            raise ValueError('Message must be str or bytes,not {mst}'.format(mst=type(message)))
        await self.frame.write(fin=fin, code=code, message=message)

    async def receive(self):
        """Get a message
        If there is no message in the message queue,
        try to read it or pop up directly from the message queue
        """
        if not self.message_queue.qsize():
            single_message = await self.frame.read()
            await self.message_queue.put(single_message)
        message = await self.message_queue.get()
        return message or None

    @property
    def get_queue_size(self):
        return self.message_queue.qsize()
