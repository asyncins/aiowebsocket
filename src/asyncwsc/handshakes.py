import re
import random
import base64

from exceptions import HandShakeError


_value_re = re.compile(rb"[\x09\x20-\x7e\x80-\xff]*")


class HandShake:
    """客户端与服务端握手操作"""
    def __init__(self, remote, reader, writer, headers=None):
        self.remote = remote
        self.write = writer
        self.reader = reader
        self.headers = headers

    @staticmethod
    def shake_headers(host: str, port: int, resource: str = '/',
                      version: int = 13, headers: list = []):
        """握手时所用的请求头信息"""
        if headers:
            return '\r\n'.join(headers)  # 允许使用自定义头信息

        bytes_key = bytes(random.getrandbits(8) for _ in range(16))
        key = base64.b64encode(bytes_key).decode()
        headers = ['GET {resource} HTTP/1.1'.format(resource=resource),
                   'Host: {host}:{port}'.format(host=host, port=port),
                   'Upgrade: websocket',
                   'Connection: Upgrade',
                   'User-Agent: Python/3.7 websockets/7.0',
                   'Sec-WebSocket-Key: {key}'.format(key=key),
                   'Sec-WebSocket-Protocol: chat, superchat',
                   'Sec-WebSocket-Version: {version}'.format(version=version),
                   '\r\n']
        return '\r\n'.join(headers)

    async def shake_(self):
        """ 握手操作 """
        porn, host, port, resource, users = self.remote
        handshake_info = self.shake_headers(host=host, port=port,
                                            resource=resource, headers=self.headers)
        self.write.write(data=handshake_info.encode())

    async def shake_result(self):
        """握手结果"""
        header = []
        for _ in range(2**8):
            result = await self.reader.readline()
            header.append(result)
            if result == b'\r\n':
                break
        if not header:
            raise HandShakeError('HandShake not response')
        protocols, socket_code = header[0].decode('utf-8').split()[:2]
        if protocols != "HTTP/1.1":
            raise HandShakeError("Unsupported HTTP version: %r" % protocols)
        socket_code = int(socket_code)
        if not 100 <= socket_code < 1000:
            raise HandShakeError("Unsupported HTTP status code: %d" % socket_code)
        return socket_code

