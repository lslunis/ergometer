import os
from subprocess import run


def mtime(path):
    return os.stat(path).st_mtime_ns


if mtime("activity_monitor.exe") < mtime("activity_monitor.cpp"):
    run("build_activity_monitor.bat")
