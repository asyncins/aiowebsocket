"""
      0                   1                   2                   3
      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
     +-+-+-+-+-------+-+-------------+-------------------------------+
     |F|R|R|R| opcode|M| Payload len |    Extended payload length    |
     |I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
     |N|V|V|V|       |S|             |   (if payload len==126/127)   |
     | |1|2|3|       |K|             |                               |
     +-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
     |     Extended payload length continued, if payload len == 127  |
     + - - - - - - - - - - - - - - - +-------------------------------+
     |                               |Masking-key, if MASK set to 1  |
     +-------------------------------+-------------------------------+
     | Masking-key (continued)       |          Payload Data         |
     +-------------------------------- - - - - - - - - - - - - - - - +
     :                     Payload Data continued ...                :
     + - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
     |                     Payload Data continued ...                |
     +---------------------------------------------------------------+

    FIN:  1 bit

      Indicates that this is the final fragment in a message.  The first
      fragment MAY also be the final fragment.

   RSV1, RSV2, RSV3:  1 bit each

      MUST be 0 unless an extension is negotiated that defines meanings
      for non-zero values.  If a nonzero value is received and none of
      the negotiated extensions defines the meaning of such a nonzero
      value, the receiving endpoint MUST _Fail the WebSocket
      Connection_.

   Opcode:  4 bits

      Defines the interpretation of the "Payload data".  If an unknown
      opcode is received, the receiving endpoint MUST _Fail the
      WebSocket Connection_.  The following values are defined.

      *  %x0 denotes a continuation frame

      *  %x1 denotes a text frame

      *  %x2 denotes a binary frame

      *  %x3-7 are reserved for further non-control frames

      *  %x8 denotes a connection close

      *  %x9 denotes a ping

      *  %xA denotes a pong

      *  %xB-F are reserved for further control frames

   Mask:  1 bit

      Defines whether the "Payload data" is masked.  If set to 1, a
      masking key is present in masking-key, and this is used to unmask
      the "Payload data" as per Section 5.3.  All frames sent from
      client to server have this bit set to 1.

   Payload length:  7 bits, 7+16 bits, or 7+64 bits

      The length of the "Payload data", in bytes: if 0-125, that is the
      payload length.  If 126, the following 2 bytes interpreted as a
      16-bit unsigned integer are the payload length.  If 127, the
      following 8 bytes interpreted as a 64-bit unsigned integer (the
      most significant bit MUST be 0) are the payload length.  Multibyte
      length quantities are expressed in network byte order.  Note that
      in all cases, the minimal number of bytes MUST be used to encode
      the length, for example, the length of a 124-byte-long string
      can't be encoded as the sequence 126, 0, 124.  The payload length
      is the length of the "Extension data" + the length of the
      "Application data".  The length of the "Extension data" may be
      zero, in which case the payload length is the length of the
      "Application data".

   Masking-key:  0 or 4 bytes

      All frames sent from the client to the server are masked by a
      32-bit value that is contained within the frame.  This field is
      present if the mask bit is set to 1 and is absent if the mask bit
      is set to 0.  See Section 5.3 for further information on client-
      to-server masking.

   Payload data:  (x+y) bytes

      The "Payload data" is defined as "Extension data" concatenated
      with "Application data".

   Extension data:  x bytes

      The "Extension data" is 0 bytes unless an extension has been
      negotiated.  Any extension MUST specify the length of the
      "Extension data", or how that length may be calculated, and how
      the extension use MUST be negotiated during the opening handshake.
      If present, the "Extension data" is included in the total payload
      length.

   Application data:  y bytes

      Arbitrary "Application data", taking up the remainder of the frame
      after any "Extension data".  The length of the "Application data"
      is equal to the payload length minus the length of the "Extension
      data".

"""

import io
import random
import logging
from struct import pack, unpack
from itertools import cycle
from .enumerations import *
from .exceptions import FrameError


class Frames:
    """数据帧相关操作"""
    def __init__(self, reader: object, writer: object):
        self.reader = reader
        self.writer = writer
        self.maxsize = 2**64

    @staticmethod
    def message_mask(message: bytes, mask):
        """The masking key is contained completely within the frame, as defined
       in Section 5.2 as frame-masking-key.  It is used to mask the "Payload
       data" defined in the same section as frame-payload-data, which
       includes "Extension data" and "Application data".

       The masking key is a 32-bit value chosen at random by the client.
       When preparing a masked frame, the client MUST pick a fresh masking
       key from the set of allowed 32-bit values.  The masking key needs to
       be unpredictable; thus, the masking key MUST be derived from a strong
       source of entropy, and the masking key for a given frame MUST NOT
       make it simple for a server/proxy to predict the masking key for a
       subsequent frame.  The unpredictability of the masking key is
       essential to prevent authors of malicious applications from selecting
       the bytes that appear on the wire.  RFC 4086 [RFC4086] discusses what
       entails a suitable source of entropy for security-sensitive
       applications.

       The masking does not affect the length of the "Payload data".  To
       convert masked data into unmasked data, or vice versa, the following
       algorithm is applied.  The same algorithm applies regardless of the
       direction of the translation, e.g., the same steps are applied to
       mask the data as to unmask the data.

       Octet i of the transformed data ("transformed-octet-i") is the XOR of
       octet i of the original data ("original-octet-i") with octet at index
       i modulo 4 of the masking key ("masking-key-octet-j"):
         j = i MOD 4
         transformed-octet-i = original-octet-i XOR masking-key-octet-j

       The payload length, indicated in the framing as frame-payload-length,
       does NOT include the length of the masking key.  It is the length of
       the "Payload data", e.g., the number of bytes following the masking
       key.
   """
        if len(mask) != 4:
            raise FrameError("The 'mask' must contain 4 bytes")
        return bytes(b ^ m for b, m in zip(message, cycle(mask)))

    async def pong(self, message: bytes = b''):
        """大太监彭公公
        The Pong frame contains an opcode of 0xA.
        Section 5.5.2 details requirements that apply to both Ping and Pong
        frames.
        A Pong frame sent in response to a Ping frame must have identical
        "Application data" as found in the message body of the Ping frame
        being replied to.
        If an endpoint receives a Ping frame and has not yet sent Pong
        frame(s) in response to previous Ping frame(s), the endpoint MAY
        elect to send a Pong frame for only the most recently processed Ping
        frame.
        """
        await self.write(fin=True, code=ControlFrames.pong.value, message=message)

    async def extra_operation(self, code: int, message: bytes):
        """Judge whether additional operations are
        required based on the DataFrame
        For example, close the connection or call pong
        """
        if code not in DataFrames._value2member_map_:
            if code is ControlFrames.ping.value:
                await self.pong(message=message)
            elif code is ControlFrames.close.value:
                await self.receive_close()
            else:
                raise FrameError('Invalid operation code.')

    async def unpack_frame(self, mask=False, maxsize=None):
        """Unpack data frame,data frame unmasked return from server
        so when unpacking, mask is false.

        This wire format for the data transfer part is described by the ABNF
        [RFC5234] given in detail in this section.  (Note that, unlike in
        other sections of this document, the ABNF in this section is
        operating on groups of bits.  The length of each group of bits is
        indicated in a comment.  When encoded on the wire, the most
        significant bit is the leftmost in the ABNF).  A high-level overview
        of the framing is given in the following figure.  In a case of
        conflict between the figure below and the ABNF specified later in
        this section, the figure is authoritative.
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
        if maxsize and length > maxsize:
            raise FrameError("Message length is too long)".format(length, maxsize))
        if mask:
            mask_bits = await reader(4)
        message = self.message_mask(message, mask_bits) if mask else await reader(length)
        return fin, code, rsv1, rsv2, rsv3, message

    async def read(self, text=False, mask=False, maxsize=None):
        """return information about message
        """
        fin, code, rsv1, rsv2, rsv3, message = await self.unpack_frame(mask, maxsize)
        await self.extra_operation(code, message)  # 根据操作码决定后续操作
        if any([rsv1, rsv2, rsv3]):
            logging.warning('RSV not 0')
        if not fin:
            logging.warning('Fragmented control frame:Not FIN')
        if code is DataFrames.binary.value and text:
            if isinstance(message, bytes):
                message = message.decode()
        if code is DataFrames.text.value and not text:
            if isinstance(message, str):
                message = message.encode()
        return message

    @staticmethod
    def pack_message(fin, code, mask, rsv1=0, rsv2=0, rsv3=0):
        """Converting message into data frames
        conversion rule reference document:
        https://tools.ietf.org/html/rfc6455#section-5.2
        """
        head1 = (
                (0b10000000 if fin else 0)
                | (0b01000000 if rsv1 else 0)
                | (0b00100000 if rsv2 else 0)
                | (0b00010000 if rsv3 else 0)
                | code
        )
        head2 = 0b10000000 if mask else 0  # Whether to mask or not
        return head1, head2

    async def write(self, fin, code, message, mask=True, rsv1=0, rsv2=0, rsv3=0):
        """Converting messages to data frames and sending them.
        Client data frames must be masked,so mask is True.
        """
        head1, head2 = self.pack_message(fin, code, mask, rsv1, rsv2, rsv3)
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

        if mask:
            # pack mask
            mask_bits = pack('!I', random.getrandbits(32))
            output.write(mask_bits)
            message = self.message_mask(message, mask_bits)

        output.write(message)
        self.writer.write(output.getvalue())

    async def receive_close(self):
        """ When you receive a message that
        the server closes the connection, you
        can do something here """
