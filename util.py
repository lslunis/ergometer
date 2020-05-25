import asyncio
from warnings import warn
from functools import wraps


def retry_on(Error, return_on_success=False, retry_delay=None):
    def curry(loop):
        @wraps(loop)
        async def retry_loop(*args, **kwargs):
            while True:
                try:
                    value = await loop(*args, **kwargs)
                    if return_on_success:
                        return value
                except FatalError as fe:
                    raise
                except Error as e:
                    warn(e)
                    if retry_delay is not None:
                        await asyncio.sleep(retry_delay)

        return retry_loop

    return curry


def retry_on_iter(Error, retry_delay=None):
    def curry(loop):
        @wraps(loop)
        async def retry_loop(*args, **kwargs):
            while True:
                try:
                    async for item in loop(*args, **kwargs):
                        yield item
                except FatalError as fe:
                    raise
                except Error as e:
                    warn(e)
                    if retry_delay is not None:
                        await asyncio.sleep(retry_delay)

        return retry_loop

    return curry


class PositionError(Exception):
    pass


def die_unless(cond, message):
    if not cond:
        raise Exception(message)


class FatalError(Exception):
    pass
