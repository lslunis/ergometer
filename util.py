import asyncio
import logging
import os
import sys
from collections import namedtuple
from functools import wraps
from itertools import takewhile
from warnings import warn

log = logging.getLogger("ergometer")


class FatalError(Exception):
    ...


class PositionError(Exception):
    ...


def die_unless(cond, message):
    if not cond:
        raise Exception(message)


class Interval(namedtuple("Interval", ["start", "end"])):
    def overlaps(self, *args):
        other = Interval(*args)
        return self.start < other.start < self.end or self.start < other.end < self.end


def pairwise(iterable):
    iterator = iter(iterable)
    return zip(iterator, iterator)


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
                    log.error(e)
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
                    log.error(e)
                    if retry_delay is not None:
                        await asyncio.sleep(retry_delay)

        return retry_loop

    return curry


def takeuntil_inclusive(predicate, iterable):
    for x in iterable:
        yield x
        if predicate(x):
            return


def init():
    # Set cwd to data directory.
    os.chdir(os.path.join(os.path.dirname(__file__), sys.argv[1]))

    # Set up logging.
    formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    log.setLevel(logging.DEBUG)
    for level in (logging.DEBUG, logging.ERROR):
        handler = logging.FileHandler(logging.getLevelName(level) + ".log")
        handler.setFormatter(formatter)
        handler.setLevel(level)
        log.addHandler(handler)
    log.info("Ergometer starting")
