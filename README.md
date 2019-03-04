
# aiowebsocket: Asynchronous websocket client

AioWebSocket is an asynchronous WebSocket client that 

follows the WebSocket specification and is lighter and faster than other libraries.

AioWebSocket是一个遵循 WebSocket 规范的

异步 WebSocket 客户端，相对于其他库它更轻、更快。

![images](https://github.com/asyncins/asyncwsc/blob/master/images/aiowebsocket.jpg)

```
Why is it Lighter？
Code volume just 30 KB
Why is it Faster？
it is based on asyncio and asynchronous
```

# Installation

```
pip install aiowebsocket
```

# Usage(ws)

```
import asyncio
import logging
from datetime import datetime
from aiowebsocket.converses import AioWebSocket


async def startup(uri):
    async with AioWebSocket(uri) as aws:
        converse = aws.manipulator
        message = b'AioWebSocket - Async WebSocket Client'
        while True:
            await converse.send(message)
            print('{time}-Client send: {message}'
                  .format(time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), message=message))
            mes = await converse.receive()
            print('{time}-Client receive: {rec}'
                  .format(time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), rec=mes))


if __name__ == '__main__':
    remote = 'ws://echo.websocket.org'
    try:
        asyncio.get_event_loop().run_until_complete(startup(remote))
    except KeyboardInterrupt as exc:
        logging.info('Quit.')

```

# wss

The relationship between WSS and WS is just like HTTPS and HTTP. If you need to use the WSS protocol

just need to add SSL = True when connecting:

```
import asyncio
import logging
from datetime import datetime
from aiowebsocket.converses import AioWebSocket


async def startup(uri):
    async with AioWebSocket(uri, ssl=True) as aws:
        converse = aws.manipulator
        message = b'AioWebSocket - Async WebSocket Client'
        while True:
            await converse.send(message)
            print('{time}-Client send: {message}'
                  .format(time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), message=message))
            mes = await converse.receive()
            print('{time}-Client receive: {rec}'
                  .format(time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), rec=mes))


if __name__ == '__main__':
    remote = 'wss://echo.websocket.org'
    try:
        asyncio.get_event_loop().run_until_complete(startup(remote))
    except KeyboardInterrupt as exc:
        logging.info('Quit.')

```

# 开发故事

在开发 aiowebsocket 库之前，我参考了 websocket-client 和 websockets 这两个库，在阅读过源码以及使用过后觉得 WebSocket 的连接应该与这两个库一样方便，但是在速度和代码结构上还可以更清晰，所以在完全不懂 WebSocket 的情况下通过阅读、调试源码以及翻阅资料：

* Python 网络和进程间通信 https://docs.python.org/3/library/ipc.html
* WebSocket 规范 https://tools.ietf.org/html/rfc6455#section-1.2
* websocket-client https://github.com/websocket-client/websocket-client
* WebSockets https://github.com/aaugustin/websockets
* Python Web学习笔记之WebSocket 通信过程与实现 https://www.cnblogs.com/JetpropelledSnake/p/9033064.html#_label1
* python---websocket的使用 https://www.cnblogs.com/ssyfj/p/9245150.html

最终用了 7 天时间完成 aiowebsocket 库的设计和开发。下图是 aiowebsocket 库文件结构以及类的设计图：

![images](https://github.com/asyncins/asyncwsc/blob/master/images/aiowebsocket-class.png)

相比 websockets 库的结构，asyncwsc 文件结构非常清晰，并且代码量很少。由于 websockets 库用的是 asyncio 旧语法，并且通过 StreameProtocol
协议，实现自定义协议，加上功能设计不明确，所以导致它的结构比较混乱。整个 websockets 库的源码图我没有画出，但是在调试时候有绘制改进图，StreameProtocol 协议（改进草图）类似下图：

![images](https://github.com/asyncins/asyncwsc/blob/master/images/WebSocketsCommonProtocol.png)

这仅仅是协议的改进草稿，实际上源码的逻辑更为混乱。

# WebSocket 及协议相关知识

WebSocket status Code [tools.ietf.org](https://tools.ietf.org/html/rfc6455#section-7.4.1)

状态码 | 名称 |  含义描述  
-|-|-
0~999 |  | 保留使用 |
1000 | CLOSE_NORMAL | 正常关闭; 无论为何目的而创建, 该链接都已成功完成任务. |
1001 | CLOSE_GOING_AWAY | 终端离开, 可能因为服务端错误, 也可能因为浏览器正从打开连接的页面跳转离开. |
1002 |	CLOSE_PROTOCOL_ERROR |	由于协议错误而中断连接.
1003 |	CLOSE_UNSUPPORTED |	由于接收到不允许的数据类型而断开连接 (如仅接收文本数据的终端接收到了二进制数据).
1004 |		              | 保留. 其意义可能会在未来定义.
1005 |	CLOSE_NO_STATUS |	保留. 表示没有收到预期的状态码.
1006 |	CLOSE_ABNORMAL |	保留. 用于期望收到状态码时连接非正常关闭 (也就是说, 没有发送关闭帧).
1007 |	Unsupported Data |	由于收到了格式不符的数据而断开连接 (如文本消息中包含了非 UTF-8 数据).
1008 |	Policy Violation |	由于收到不符合约定的数据而断开连接. 这是一个通用状态码, 用于不适合使用 1003 和 1009 状态码的场景.
1009 |	CLOSE_TOO_LARGE |	由于收到过大的数据帧而断开连接.
1010 |	Missing Extension |	客户端期望服务器商定一个或多个拓展, 但服务器没有处理, 因此客户端断开连接.
1011 |	Internal Error |	客户端由于遇到没有预料的情况阻止其完成请求, 因此服务端断开连接.
1012 |	Service Restart |	服务器由于重启而断开连接.
1013 |	Try Again Later |	服务器由于临时原因断开连接, 如服务器过载因此断开一部分客户端连接.
1014 |		            |由 WebSocket标准保留以便未来使用.
1015 |	TLS Handshake   |保留. 表示连接由于无法完成 TLS 握手而关闭 (例如无法验证服务器证书).
1000–2999 |		 |保留用于定义此协议，其未来的修订版和在。中指定的扩展名永久和随时可用的公共规范。
3000–3999 |		 |保留供使用库/框架/应用程序。这些状态代码是直接在IANA注册。这些代码的解释该协议未定义。
4000–4999 |		 |保留供私人使用因此无法注册。这些代码可以由先前使用WebSocket应用程序之间的协议。解释这个协议未定义这些代码。
