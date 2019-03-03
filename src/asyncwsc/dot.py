import asyncio


async def eternity():
    # Sleep for one hour
    await asyncio.sleep(360)
    print('yay!')


async def main():
    # Wait for at most 1 second
    try:
        await asyncio.wait_for(eternity(), timeout=1.0)
    except asyncio.TimeoutError:
        print('timeout!')


async def prints():
    await asyncio.sleep(1)
    print('5566')


async def tips():
    sleeps = 3
    sizes = 20
    while True:
        await asyncio.sleep(2)
        print('This sizes: %s' % sizes)
        await asyncio.sleep(sleeps)
        print('...Sleep sizes: %s' % (sizes-sleeps))
        sizes = 20
        print('F5 sizes: %s' % sizes)
        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(loop.close())


asyncio.get_event_loop().run_until_complete(tips())

# Expected output:
#
#     timeout!