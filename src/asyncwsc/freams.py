import io
import random
import itertools

from struct import pack, unpack
from collections import namedtuple
from .exceptions import *
from .parts import apply_mask, DATA_CODE, CTRL_CODE
from .protocols import SocketState


EXTERNAL_CLOSE_CODES = [1000, 1001, 1002, 1003, 1007, 1008, 1009, 1010, 1011]
FrameData = namedtuple('FrameData', ['fin', 'code', 'data', 'rsv1', 'rsv2', 'rsv3'])


class Frames(FrameData):
    """WebSocket frame.
    * ``fin`` is the FIN bit
    * ``rsv1`` is the RSV1 bit
    * ``rsv2`` is the RSV2 bit
    * ``rsv3`` is the RSV3 bit
    * ``code`` is the opcode
    * ``data`` is the payload data
    """
    def __new__(cls, fin, code, data, rsv1=False, rsv2=False, rsv3=False):
        return FrameData.__new__(cls, fin, code, data, rsv1, rsv2, rsv3)

    @staticmethod
    def serialize_close_frame(code, reason):
        if not (code in EXTERNAL_CLOSE_CODES or 3000 <= code < 5000):
            raise StatusCodeError("Invalid status code")
        return pack('!H', code) + reason.encode('utf-8')

    @classmethod
    async def read(cls, reader, *, mask, max_size=None, extensions=None):
        """读取WebSocket帧并返回Frame对象
        ``reader`` 是一个协程对象
        """
        frame_header = await reader(2)  # 读取帧头
        head1, head2 = unpack('!BB', frame_header)

        # 编码
        fin = True if head1 & 0b10000000 else False
        rsv1 = True if head1 & 0b01000000 else False
        rsv2 = True if head1 & 0b00100000 else False
        rsv3 = True if head1 & 0b00010000 else False
        code = head1 & 0b00001111

        if (True if head2 & 0b10000000 else False) != mask:
            raise UnKnownError("Incorrect masking")

        length = head2 & 0b01111111
        if length == 126:
            data = await reader(2)
            length, = unpack('!H', data)
        elif length == 127:
            data = await reader(8)
            length, = unpack('!Q', data)
        if max_size is not None and length > max_size:
            raise PayloadError(
                "Payload length exceeds size limit ({} > {} bytes)"
                .format(length, max_size))
        if mask:
            mask_bits = await reader(4)

        # Read the data.
        data = apply_mask(data, mask_bits) if mask else await reader(length)
        frame = cls(fin, code, data, rsv1, rsv2, rsv3)
        extensions = extensions or []
        for extension in reversed(extensions):
            frame = extension.decode(frame, max_size=max_size)
        frame.check()
        return frame

    def check(self):
        """ 校验frame
        """
        if self.rsv1 or self.rsv2 or self.rsv3:
            raise ValueError("Reserved bits must be 0")

        if self.code in DATA_CODE:
            return
        elif self.code in CTRL_CODE:
            if len(self.data) > 125:
                raise FrameError("Control frame too long")
            if not self.fin:
                raise FrameError("Fragmented control frame")
        else:
            raise UnverifiedError("Invalid code: {}".format(self.code))

    def write(self, writer, mask, extensions=None):
        """ Write a WebSocket frame.
        """
        self.check()

        if extensions is None:
            extensions = []
        for extension in extensions:
            frame = extension.encode(frame)

        output = io.BytesIO()

        # Prepare the header.
        head1 = (
                (0b10000000 if frame.fin else 0)
                | (0b01000000 if frame.rsv1 else 0)
                | (0b00100000 if frame.rsv2 else 0)
                | (0b00010000 if frame.rsv3 else 0)
                | frame.opcode
        )

        head2 = 0b10000000 if mask else 0

        length = len(frame.data)
        if length < 126:
            output.write(pack('!BB', head1, head2 | length))
        elif length < 65536:
            output.write(pack('!BBH', head1, head2 | 126, length))
        else:
            output.write(pack('!BBQ', head1, head2 | 127, length))

        if mask:
            mask_bits = pack('!I', random.getrandbits(32))
            output.write(mask_bits)

        # Prepare the data.
        if mask:
            data = apply_mask(frame.data, mask_bits)
        else:
            data = frame.data
        print(output.write(data))

        # Send the frame.

        # The frame is written in a single call to writer in order to prevent
        # TCP fragmentation. See #68 for details. This also makes it safe to
        # send frames concurrently from multiple coroutines.
        writer(output.getvalue())

    async def write_frame(self, fin: bool, code: int, data: bytes, *args,
                          _expected_state: int = SocketState.open):
        # Defensive assertion for protocol compliance.
        if self.state is not _expected_state:  # pragma: no cover
            raise UnverifiedError(
                f"Cannot write to a WebSocket in the {self.state.name} state")

        self.write(self.writer.write, mask=self.is_client, extensions=self.extensions)

        try:
            # drain() cannot be called concurrently by multiple coroutines:
            # http://bugs.python.org/issue29930. Remove this lock when no
            # version of Python where this bugs exists is supported anymore.
            async with self._drain_lock:
                # Handle flow control automatically.
                await self.writer.drain()
        except ConnectionError:
            # Terminate the connection if the socket died.
            self.fail_connection()
            # Wait until the connection is closed to raise ConnectionClosed
            # with the correct code and reason.

    async def read_frame(self, max_size: int):
        """
        Read a single frame from the connection.

        """
        frame = await Frame.read(
            self.reader.readexactly,
            mask=not self.is_client,
            max_size=max_size,
            extensions=self.extensions,
        )
        logger.debug("%s < %r", self.side, frame)
        return frame
