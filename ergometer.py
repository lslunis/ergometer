from asyncio import sleep
from time import time

async def read_input():
    while True:
        now = round(time())
        await emit(f'{now} 1 h\n')
        await sleep(2)
