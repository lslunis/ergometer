import argparse
import asyncio
import json
import logging
import logging.handlers
import math
import os
import re
import sys
from collections import namedtuple
from functools import wraps
from urllib.parse import ParseResult, urlunparse

log = logging.getLogger("ergometer")


class FatalError(Exception):
    ...


class PositionError(Exception):
    ...


def clip(value, low=-math.inf, high=math.inf):
    return max(low, min(high, value))


def die_unless(cond, message=""):
    if not cond:
        raise FatalError(message)


class Interval(namedtuple("Interval", ["start", "end"])):
    def overlaps(self, *args):
        other = Interval(*args)
        return self.start < other.start < self.end or self.start < other.end < self.end


def init():
    config = {
        "button_count_ignore_list": [],
        "data": "",
        "generate_activity": False,
        "log": 10,
        "source_root": getattr(
            sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ),
        "verbose": False,
    }
    config_path = os.path.join(config["source_root"], "config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            config.update(json.load(f))
    p = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    p.add_argument("--button_count_ignore_list", nargs="+", type=int)
    p.add_argument("--data")
    p.add_argument("--generate_activity", action="store_true")
    p.add_argument("--log", type=int)
    p.add_argument("--server")
    p.add_argument("--verbose", action="store_true")
    config.update(vars(p.parse_args()))

    storage_root = os.path.join(config["source_root"], "data", config["data"])
    os.makedirs(storage_root, exist_ok=True)
    os.chdir(storage_root)

    loggers = (
        [
            logging.getLogger(name)
            for name in [None, "asyncio", "sqlalchemy.engine", "websockets"]
        ]
        if config["verbose"]
        else [log]
    )
    for logger in loggers:
        logger.setLevel(config["log"])
    root = loggers[0]
    formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)
    file = logging.handlers.RotatingFileHandler(
        "ergometer.log", maxBytes=int(1e7), backupCount=1
    )
    file.setFormatter(formatter)
    root.addHandler(file)

    log.info("Ergometer starting")
    return config


def lerp(x, x0, x1, y0, y1):
    return (x - x0) * (y1 - y0) / (x1 - x0)


def log_exceptions(fn):
    @wraps(fn)
    def logged(*args, **kw):
        try:
            return fn(*args, **kw)
        except:
            log.exception("unexpected error")
            raise

    return logged


def async_log_exceptions(fn):
    @wraps(fn)
    async def logged(*args, **kw):
        try:
            return await fn(*args, **kw)
        except asyncio.CancelledError:
            raise
        except:
            log.exception("unexpected error")
            raise

    return logged


def pairwise(iterable):
    iterator = iter(iterable)
    return zip(iterator, iterator)


def retry_on(Error, return_on_success=False, retry_delay=5):
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
                    log.debug(f"retrying: {e}")
                    if retry_delay is not None:
                        await asyncio.sleep(retry_delay)

        return retry_loop

    return curry


def retry_on_iter(Error, retry_delay=5):
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
                    log.debug(f"retrying: {e}")
                    if retry_delay is not None:
                        await asyncio.sleep(retry_delay)

        return retry_loop

    return curry


def takeuntil_inclusive(predicate, iterable):
    for x in iterable:
        yield x
        if predicate(x):
            return


def until_error(f, E):
    try:
        while True:
            yield f()
    except E:
        ...
