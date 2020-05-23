import asyncio


async def read_subprocess(cmd, broker):
    proc = await asyncio.create_subprocess_exec(
        cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    while True:
        event = await proc.stdout.readline()
        if not event.endswith("\n"):
            raise ValueError(f"truncated event: {event!r}")
        broker.publish(event)
