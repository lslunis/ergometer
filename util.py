from functools import wraps


def retry_on(Error):
    def curry(loop):
        @wraps(loop)
        async def retry_loop(*args, **kwargs):
            while True:
                try:
                    loop(*args, **kwargs)
                except Error as e:
                    warn(e)

        return retry_loop

    return curry


class PositionError(Exception):
    pass


def die_unless(cond, message):
    if not cond:
        raise Exception(message)
