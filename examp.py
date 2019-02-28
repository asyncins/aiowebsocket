import asyncio


async def transfer(val):
    print(val)
    return val + 1


async def tra():
    task = asyncio.create_task(transfer(5))
    # task.cancel()


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(tra())
