from struct import pack, unpack
import random
import asyncio
import logging

from .parts import PING, PONG

from .protocols import AsyncWebSocketStreamReaderProtocol


class RespBeat:
    """ ping pong """

    def __int__(self, protocols):
        self.protocols = AsyncWebSocketStreamReaderProtocol()

    async def ping(self, data=None):
        """
        This coroutine sends a ping.

        It returns a :class:`~asyncio.Future` which will be completed when the
        corresponding pong is received and which you may ignore if you don't
        want to wait.

        A ping may serve as a keepalive or as a check that the remote endpoint
        received all messages up to this point::

            pong_waiter = await ws.ping()
            await pong_waiter   # only if you want to wait for the pong

        By default, the ping contains four random bytes. The content may be
        overridden with the optional ``data`` argument which must be of type
        :class:`str` (which will be encoded to UTF-8) or :class:`bytes`.
        """
        await self.protocols.ensure_open()

        if data is not None:
            data = self.protocols.encode_data(data)

        # Protect against duplicates if a payload is explicitly set.
        if data in self.pings:
            raise ValueError("Already waiting for a pong with the same data")

        # Generate a unique random payload otherwise.
        while data is None or data in self.pings:
            data = pack('!I', random.getrandbits(32))

        self.pings[data] = asyncio.Future(loop=self.loop)

        await self.protocols.write_frame(True, PING, data)

        return asyncio.shield(self.pings[data])

    async def pong(self, data=b''):
        """
        This coroutine sends a pong.

        An unsolicited pong may serve as a unidirectional heartbeat.

        The content may be overridden with the optional ``data`` argument
        which must be of type :class:`str` (which will be encoded to UTF-8) or
        :class:`bytes`.

        """
        await self.protocols.ensure_open()

        data = self.protocols.encode_data(data)

        await self.protocols.write_frame(True, PONG, data)

    async def keep_alive_ping(self):
        """Send a Ping frame and wait for a Pong frame at regular intervals.
        """
        if self.ping_interval is None:
            return

        try:
            while True:
                await asyncio.sleep(self.ping_interval, loop=self.loop)

                # ping() cannot raise ConnectionClosed, only CancelledError:
                # - If the connection is CLOSING, keepalive_ping_task will be
                #   canceled by close_connection() before ping() returns.
                # - If the connection is CLOSED, keepalive_ping_task must be
                #   canceled already.
                ping_waiter = await self.ping()

                if self.ping_timeout is not None:
                    try:
                        await asyncio.wait_for(
                            ping_waiter, self.ping_timeout, loop=self.loop
                        )
                    except asyncio.TimeoutError:
                        self.fail_connection(1011)
                        break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.warning("Unexpected exception in keep alive ping task", exc_info=True)

    def abort_keep_alive_pings(self):
        """
        Raise ConnectionClosed in pending keepalive pings.

        They'll never receive a pong once the connection is closed.

        """
        assert self.state is SocketState.closed
        exc = ConnectionClosed(self.close_code, self.close_reason)
        exc.__cause__ = self.transfer_data_exc  # emulate raise ... from ...
        for ping in self.pings.values():
            ping.set_exception(exc)
        # if self.pings:
        #     pings_hex = ', '.join(
        #         binascii.hexlify(ping_id).decode() or '[empty]'
        #         for ping_id in self.pings
        #     )
        #     plural = 's' if len(self.pings) > 1 else ''