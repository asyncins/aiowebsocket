import re
import random
import base64
from asyncio import StreamWriter, StreamReader
from urllib.parse import urlparse
from collections import namedtuple

_value_re = re.compile(rb"[\x09\x20-\x7e\x80-\xff]*")
REMOTE = namedtuple('WebSocketURI', ['porn', 'host', 'port', 'resource', 'users'])


class Headers:
    def __int__(self):
        pass

    @staticmethod
    def uri_washing(uri):
        """Parse and validates the uri
        :param uri: a WebSocket URI,like:'ws://exam.com'
        :return:class-> WebSocketURI
        :raise: exceptions.Unverified
        """
        uri = urlparse(uri)
        try:
            porn = uri.scheme  # protocol name
            host = uri.hostname
            port = uri.port or (443 if porn == 'wss' else 80)
            users = None
            resource = uri.path or '/'
            if uri.query:
                resource += '?' + uri.query
            if uri.username or uri.password:
                users = (uri.username, uri.password)
        except AssertionError as exc:
            raise UnverifiedError("The '{uri}' unverified".format(uri=uri)) from exc
        return WebSocketURI(porn, host, port, resource, users)

    @staticmethod
    def construct_header(self, headers=None):
        if not headers:
            headers = {}
        bytes_key = bytes(random.getrandbits(8) for _ in range(16))
        key = base64.b64encode(bytes_key).decode()
        headers["Upgrade"] = "websocket"
        headers["Connection"] = "Upgrade"
        headers["Sec-WebSocket-Key"] = key
        headers["Sec-WebSocket-Version"] = "13"
        return headers


class HandShake:
    def __init__(self, uri, reader, writer, headers=None):
        self.uri = uri
        self.write = writer
        self.reader = reader
        self.headers = headers

    @staticmethod
    def shake_remote(uri):
        """通过拆解uri获得连接信息,对信息进行基本校验
        :param uri:'ws://exam.com'
        :return:class-> REMOTE
        :raise: exceptions.Unverified
        """
        uri = urlparse(uri)
        try:
            porn = uri.scheme  # protocol name,example: http ws wss https ftp
            host = uri.hostname
            port = uri.port or (443 if porn == 'wss' else 80)
            users = None
            resource = uri.path or '/'
            if uri.query:
                resource += '?' + uri.query
            if uri.username or uri.password:
                users = (uri.username, uri.password)
        except AssertionError as exc:
            raise ValueError("The '{uri}' unverified".format(uri=uri)) from exc
        return REMOTE(porn, host, port, resource, users)

    @staticmethod
    def shake_headers(host, port, resource='/', version=13, headers=None):
        """握手时所用的头信息"""
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

    async def handshake_(self):
        porn, host, port, resource, users = self.shake_remote(self.uri)
        handshake_info = self.shake_headers(host=host, port=port,
                                            resource=resource, headers=self.headers)
        self.write.write(data=handshake_info.encode())

    async def handshake_result(self):
        result = await self.reader.readline()
        if not result:
            raise ValueError('Not Response')
        protocols, socket_code = result.decode('utf-8').split()[:2]
        if protocols != "HTTP/1.1":
            raise ValueError("Unsupported HTTP version: %r" % pron)
        socket_code = int(socket_code)
        if not 100 <= socket_code < 1000:
            raise ValueError("Unsupported HTTP status code: %d" % socket_code)
        return socket_code

