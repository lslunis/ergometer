from ergometer.model import Model
from ergometer.util import init, log


def main():
    try:
        Model(init())
    finally:
        log.info("Ergometer exited")
