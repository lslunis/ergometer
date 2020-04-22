import aiosqlite
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


async def commit_state(broker):
    async with aiosqlite.connect("state.db") as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS "offsets" (
                "host" INTEGER PRIMARY KEY,
                "offset" INTEGER NOT NULL
            )"""
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS "targets" (
                "name" TEXT PRIMARY KEY,
                "target" INTEGER NOT NULL,
                "mtime" INTEGER NOT NULL
            ) WITHOUT ROWID"""
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS "totals" (
                "start" INTEGER PRIMARY KEY,
                "total" INTEGER NOT NULL
            )"""
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS "gaps" (
                "start" INTEGER PRIMARY KEY,
                "span" INTEGER NOT NULL
            )"""
        )
        await db.execute('''DROP INDEX IF EXISTS "rests"''')

        async with db.execute(
            """SELECT "target" FROM "targets" WHERE "name" = 'r'"""
        ) as cursor:
            async for (rest_target,) in cursor:
                pass
        await db.execute(
            f"""
            CREATE UNIQUE INDEX "rests" ON "gaps" ("start")
                WHERE "span" >= {rest_target}"""
        )
        offsets = []
        async with db.execute(
            '''SELECT "host", "offset" FROM "offsets"'''
        ) as cursor:
            async for host, offset in cursor:
                offsets.append((host, offset))
        await db.commit()
        async for x in broker.subscribe(offsets):
            pass


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
