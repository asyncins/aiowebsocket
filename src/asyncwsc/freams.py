import io
import random
import logging
from struct import pack, unpack
from itertools import cycle
from enumerations import *
from exceptions import FrameError


class Frames:
    """数据帧相关操作"""
    def __init__(self, reader: object, writer: object):
        self.reader = reader
        self.writer = writer

    @staticmethod
    def message_mask(message: bytes, mask):
        """掩码操作"""
        if len(mask) != 4:
            raise FrameError("The 'mask' must contain 4 bytes")
        return bytes(b ^ m for b, m in zip(message, cycle(mask)))

    async def pong(self, message: bytes = b''):
        """大太监彭公公"""
        await self.write(fin=True, code=CtrlCode.pong.value, message=message)

    async def extra_operation(self, code: int, message: bytes):
        """根据操作码判断是否需要进行额外的操作
        比如关闭连接或召唤彭公公
        0x09代表ping，0x08代表断开连接，0x0A代表pong
        """
        if code not in OperationCode._value2member_map_:
            if code is CtrlCode.ping.value:
                await self.pong(message=message)
            elif code is CtrlCode.close.value:
                await self.receive_close()
            else:
                raise FrameError('Invalid operation code.')

    async def unpack_frame(self, mask=False, max_size=None):
        """数据帧解包
        服务的返回的数据帧不掩码，所以解包时 mask=False
        读取数据帧头，解包并通过位运算得到fin标识、操作码以及数据长度
        """
        reader = self.reader.readexactly
        frame_header = await reader(2)
        head1, head2 = unpack('!BB', frame_header)

        fin = True if head1 & 0b10000000 else False
        rsv1 = True if head1 & 0b01000000 else False
        rsv2 = True if head1 & 0b00100000 else False
        rsv3 = True if head1 & 0b00010000 else False
        code = head1 & 0b00001111

        if (True if head2 & 0b10000000 else False) != mask:
            raise FrameError("Incorrect masking")

        length = head2 & 0b01111111
        if length == 126:
            message = await reader(2)
            length, = unpack('!H', message)
        elif length == 127:
            message = await reader(8)
            length, = unpack('!Q', message)
        if max_size is not None and length > max_size:
            raise FrameError("Message length is too long)".format(length, max_size))
        if mask:
            mask_bits = await reader(4)
        message = self.message_mask(message, mask_bits) if mask else await reader(length)
        await self.extra_operation(code, message)  # 可能需要的额外操作
        return fin, code, rsv1, rsv2, rsv3, message

    async def read(self, mask=False, max_size=None):
        """解码数据帧并返回信息
        服务的返回的数据帧不掩码，所以解码时mask=False
        """
        fin, code, rsv1, rsv2, rsv3, message = await self.unpack_frame(mask, max_size)
        await self.extra_operation(code, message)  # 根据操作码决定后续操作
        if rsv1 or rsv2 or rsv3:
            logging.warning('Rsv not 0')
        if len(message) > 125:
            logging.warning('Control frame too long')
        if not fin:
            logging.warning('Fragmented control frame')
        if code is OperationCode.binary.value:
            message = message.decode('utf-8')
        return message

    @staticmethod
    def pack_message(fin, code, rsv1=0, rsv2=0, rsv3=0, mask=True):
        """ 转成数据帧  """
        head1 = (
                (0b10000000 if fin else 0)
                | (0b01000000 if rsv1 else 0)
                | (0b00100000 if rsv2 else 0)
                | (0b00010000 if rsv3 else 0)
                | code
        )
        head2 = 0b10000000 if mask else 0  # 是否进行掩码或操作
        return head1, head2

    async def write(self, fin, code, message, rsv1=0, rsv2=0, rsv3=0, mask=True):
        """ 将消息转为数据帧并发送
        客戶端数据帧必须进行掩码 所以mask=True
        """
        head1, head2 = self.pack_message(fin, code, rsv1, rsv2, rsv3, mask)
        output = io.BytesIO()
        length = len(message)
        if length < 126:
            output.write(pack('!BB', head1, head2 | length))
        elif length < 2**16:
            output.write(pack('!BBH', head1, head2 | 126, length))
        elif length < 2**64:
            output.write(pack('!BBQ', head1, head2 | 127, length))
        else:
            raise ValueError('Message is too long')

        if mask:  # 掩码
            mask_bits = pack('!I', random.getrandbits(32))
            output.write(mask_bits)
            message = self.message_mask(message, mask_bits)

        output.write(message)
        self.writer.write(output.getvalue())

    async def receive_close(self):
        """ 收到服务端关闭连接的信息 """
