import aiosqlite
import asyncio
from collections import defaultdict
import re
import time as timelib


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
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS "offsets" (
                "host" TEXT PRIMARY KEY,
                "offset" INTEGER NOT NULL
            ) WITHOUT ROWID"""
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

        rest_target = await fetch_one(
            db.execute("""SELECT "target" FROM "targets" WHERE "name" = 'r'""")
        )
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
        pattern = re.compile(r"^(\d+) (?:(h)|([dsr])) (\d+)$", re.M)
        async for host, offset, payload in broker.subscribe(offsets):
            now = timelib.time()
            expected_offset = await fetch_one(
                db.execute(
                    """SELECT "offset" FROM "offsets" WHERE "host" = ?""", host
                ),
                0,
            )
            check(
                offset == expected_offset,
                f"expected offset {host}:{expected_offset}, got {offset}",
            )
            targets = {}
            totals = defaultdict(int)
            for (
                _,
                time_str,
                target_name,
                action_name,
                value_str,
            ) in pattern.finditer(payload):
                time = int(time_str)
                value = int(value_str)
                if target_name:
                    if (
                        target_name not in targets
                        or targets[target_name][0] < time
                    ):
                        targets[target_name] = (time, value)
                elif action_name:
                    totals[time // 300 * 300] += value
                    if now - time < 3600:
                        pass
        await db.execute(
            'INSERT OR REPLACE INTO "offsets" VALUES (?,?)', (host, offset)
        )
        for name in targets:
            time, value = targets[name]
            await db.execute("")


async def get_rest_start(db):
    await fetch_one(db.execute('SELECT MAX("start") FROM "gaps"'))


async def fetch_one(cursor, default=None):
    value = default
    async with cursor:
        async for (value,) in cursor:
            pass
    return value


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
