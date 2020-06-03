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

    run("venv/Scripts/pip install -q -r requirements.txt")


def freeze():
    run(r"venv\Scripts\pip freeze > requirements.txt", shell=True)


def test():
    run("venv/Scripts/pytest")


def upgrade():
    lines = (
        run("venv/Scripts/pip list --format freeze --outdated", capture_output=True)
        .stdout.decode("ascii")
        .splitlines()
    )
    packages = " ".join(line.partition("==")[0] for line in lines)
    if not packages:
        return
    run(f"venv/Scripts/python -m pip install --upgrade {packages}")
    freeze()


if __name__ == "__main__" and len(sys.argv) > 1:
    dict(b=build, f=freeze, t=test, u=upgrade).get(sys.argv[1][0], lambda: ...)()
