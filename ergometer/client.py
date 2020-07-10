from ergometer.model import Model
from ergometer.util import init, log


def main():
    try:
        Model(init())
    except KeyboardInterrupt:
        ...
    finally:
        log.info("Ergometer exited")
