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


async def commit_state(broker):
    async with aiosqlite.connect("state.db") as db:

        await db.execute('''DROP INDEX IF EXISTS "rests"''')

        rest_target = await fetch_one(
            db.execute("""SELECT "target" FROM "targets" WHERE "name" = 'r'""")
        )
        await db.execute(
            f"""
            CREATE UNIQUE INDEX "rests" ON "gaps" ("start")
                WHERE "span" >= {rest_target}"""
        )


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
