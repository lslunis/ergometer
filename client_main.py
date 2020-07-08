from .model import Model
from .util import init, log

try:
    Model(init())
finally:
    log.info("Ergometer exited")
