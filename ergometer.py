import asyncio


async def read_subprocess(cmd, broker):
    proc = await asyncio.create_subprocess_exec(
        cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    while True:
        message = await proc.stdout.readline()
        if not message.endswith("\n"):
            raise ValueError(f"truncated message: {message!r}")
        broker.publish(message.strip())


class Broker:
    def publish(message):
        pass


class ChangeEvent(Event):
    def __init__():
        super().__init__()
        self.set()

    async def wait():
        await super().wait()
        self.clear()
