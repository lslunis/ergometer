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
