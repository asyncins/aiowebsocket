import asyncio


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


if __name__ == '__main__':

    asyncio.get_event_loop().run_until_complete(tra())
