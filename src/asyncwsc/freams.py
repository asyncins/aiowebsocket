import io
import random
from asyncio import StreamWriter, StreamReader
from struct import pack, unpack
from collections import namedtuple
from .exceptions import *
from .parts import apply_mask
from .protocols import SocketState
from .enumerations import *


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
    # def __new__(cls, fin, code, message, rsv1=False, rsv2=False, rsv3=False):
    #     return FrameData.__new__(cls, fin, code, message, rsv1, rsv2, rsv3)
    #
    # def __init__(self):
    #     pass

    @staticmethod
    def serialize_close_frame(code, reason):
        """ 序列化关闭帧 """
        if not (code in CloseCode or 3000 <= code < 5000):
            raise StatusCodeError("Invalid status code")
        return pack('!H', code) + reason.encode('utf-8')

    def get_close_code_reason(self, data: bytes):
        """ 获取关闭状态码及原因 """
        length = len(data)
        if length >= 2:
            code, = unpack("!H", data[:2])
            self.check_close_code(code)
            reason = data[2:].decode("utf-8")
            return code, reason
        elif length == 0:
            return StatusCode.not_status.value, ""
        else:
            assert length == 1
            raise ProtocolError("Close frame too short")

    @staticmethod
    def check_close_code(code: int):
        """检查关闭状态码 """
        if not (code in CloseCode or 3000 <= code < 5000):
            raise UnverifiedError("Invalid status code")

    async def write_close_frame(self, message: bytes = b''):
        """写入关闭帧"""
        await self.write(fin=True, code=CtrlCode.close.value, message=message)

    async def read_frame(self, max_size: int):
        """ 从帧中获取数据
        根据解码后的operation code决定返回数据或执行操作
        """
        while True:
            frame = await self.read(max_size=max_size)
            if frame.code == CtrlCode.close.value:
                close_code, close_reason = self.get_close_code_reason(frame.data)
                await self.write_close_frame(frame.data)
                return None
            if frame.code == CtrlCode.ping.value:
                # 召唤彭公公回应平公公
                await self.pong(frame.data)
            return frame

    @staticmethod
    async def read(reader=StreamReader.readexactly, mask=False, max_size=None):
        """解码数据帧并返回Frame对象"""
        frame_header = await reader(2)  # 读取帧头
        head1, head2 = unpack('!BB', frame_header)

        # 解码
        fin = True if head1 & 0b10000000 else False
        rsv1 = True if head1 & 0b01000000 else False
        rsv2 = True if head1 & 0b00100000 else False
        rsv3 = True if head1 & 0b00010000 else False
        code = head1 & 0b00001111

        if (True if head2 & 0b10000000 else False) != mask:
            raise UnKnownError("Incorrect masking")

        length = head2 & 0b01111111
        if length == 126:
            message = await reader(2)
            length, = unpack('!H', message)
        elif length == 127:
            message = await reader(8)
            length, = unpack('!Q', message)
        if max_size is not None and length > max_size:
            raise PayloadError(
                "Payload length exceeds size limit ({} > {} bytes)"
                .format(length, max_size))
        if mask:
            mask_bits = await reader(4)
        message = apply_mask(message, mask_bits) if mask else await reader(length)
        if rsv1 or rsv2 or rsv3:
            raise ValueError("Reserved bits must be 0")
        if code in OperationCode._value2member_map_:
            return
        elif code in CtrlCode._value2member_map_:
            if len(message) > 125:
                raise FrameError("Control frame too long")
            if not fin:
                raise FrameError("Fragmented control frame")
        else:
            raise UnverifiedError("Invalid code: {}".format(code))
        return message

    @staticmethod
    def write(fin, code, message, rsv1=0, rsv2=0, rsv3=0, mask=True,
              writer=StreamWriter.write, extensions=[]):
        """ 写入数据帧 """
        output = io.BytesIO()
        # 准备帧头信息
        head1 = (
                (0b10000000 if fin else 0)
                | rsv1
                | rsv2
                | rsv3
                | code
        )

        head2 = 0b10000000 if mask else 0  # 是否进行掩码或操作

        length = len(message)
        if length < 126:
            output.write(pack('!BB', head1, head2 | length))
        elif length < 65536:
            output.write(pack('!BBH', head1, head2 | 126, length))
        else:
            output.write(pack('!BBQ', head1, head2 | 127, length))

        if mask:
            mask_bits = pack('!I', random.getrandbits(32))
            output.write(mask_bits)

        # 准备数据并写入帧
        if mask:
            message = apply_mask(message, mask_bits)
        else:
            message = message
        output.write(message)
        writer(output.getvalue())
