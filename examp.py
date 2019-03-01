import asyncio
from enum import *


async def transfer(val):
    print(val)
    return val + 1


async def tra():
    task = asyncio.Task(transfer(5))
    # connection_lost_waiter = asyncio.Future()
    # # connection_lost_waiter.set_result(None)
    # res = await connection_lost_waiter
    # if connection_lost_waiter.done():
    #     print('done')
    # print(res)


class OperationCode(IntEnum):
    cont, text, binary = (0x00, 0x01, 0x02)


class CtrlCode(IntEnum):
    close, ping, pong = (0x08, 0x09, 0x0A)

DATA_OPCODES = OP_CONT, OP_TEXT, OP_BINARY = 0x00, 0x01, 0x02
CTRL_OPCODES = OP_CLOSE, OP_PING, OP_PONG = 0x08, 0x09, 0x0A

if __name__ == '__main__':

    # asyncio.get_event_loop().run_until_complete(tra())
    asp = OperationCode.__members__
    print('1' in OperationCode._value2member_map_)
