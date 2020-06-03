import os
import sys
import venv
from subprocess import run

os.chdir(os.path.dirname(os.path.abspath(__file__)))


def mtime(path):
    return os.stat(path).st_mtime_ns


def build():
    if mtime("activity_monitor.exe") < mtime("activity_monitor.cpp"):
        run("build_activity_monitor.bat")

    if not os.path.exists("venv/pyvenv.cfg"):
        venv.create("venv", with_pip=True)

    run("venv/Scripts/pip install -r requirements.txt")


if __name__ == "__main__" and len(sys.argv) > 1:
    dict(b=build).get(sys.argv[1][0], lambda: ...)()
