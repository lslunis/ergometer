#!/usr/bin/env python3

import argparse
import math
import os
import sys
import venv
from glob import glob
from subprocess import run as execute

os.chdir(os.path.dirname(os.path.abspath(__file__)))
is_windows = os.name == "nt"
get_venv_name = lambda name: "ui" if name == "ui" else "cli"


def get_deps(venv_name):
    deps = ["pytest", "SQLAlchemy", "websockets"]
    if venv_name == "ui":
        deps += ["wxPython"]
    return deps


def mtime(path):
    return os.stat(path).st_mtime_ns if os.path.exists(path) else -math.inf


def ensure_venv(name):
    path = os.path.join("venv", name)
    if not os.path.exists(os.path.join(path, "pyvenv.cfg")):
        venv.create(path, with_pip=True)


def get_bin_path(venv_name, bin_name):
    return os.path.join(
        "venv", venv_name, "Scripts" if is_windows else "bin", bin_name,
    )


def build(name, upgrade):
    if is_windows and mtime("activity_monitor.exe") < mtime("activity_monitor.cpp"):
        execute("cmd.exe /c build_activity_monitor.bat".split())
    venv_name = get_venv_name(name)
    ensure_venv(venv_name)

    def pip(args_str):
        execute(f"{get_bin_path(venv_name, 'pip')} {args_str}", shell=True)

    requirements = f"requirements_{venv_name}.txt"
    if upgrade or not os.path.exists(requirements):
        pip(f"install --upgrade {' '.join(get_deps(venv_name))}")
        pip(f"freeze > {requirements}")
    else:
        pip(f"install -q -r {requirements}")


def fix():
    sources = glob("*.py") + glob("ergometer/**/*.py", recursive=True)
    for command in ["isort", "black"]:
        execute([command, *sources])


def run(name, args):
    python = get_bin_path(get_venv_name(name), "pythonw" if is_windows else "python3")
    execute([python, f"ergometer_{name}.py", *args])


def test(args):
    pytest = get_bin_path("cli", "pytest")
    execute([pytest, *args])


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    def register(fn, named=False):
        p = subparsers.add_parser(fn.__name__)
        p.set_defaults(command=fn)
        if named:
            p.add_argument("name", choices="client server ui".split())
        return p

    p = register(build, named=True)
    p.add_argument("--upgrade", action="store_true")

    register(fix)

    p = register(run, named=True)
    p.add_argument("args", nargs=argparse.REMAINDER)

    p = register(test)
    p.add_argument("args", nargs=argparse.REMAINDER)

    kw = vars(parser.parse_args())

    if (
        kw.get("name") == "ui"
        and not is_windows
        and not execute(["python.exe", "do.py", *sys.argv[1:]]).returncode
    ):
        return  # succeeded in running the Windows version instead

    try:
        kw.pop("command")(**kw)
    except KeyboardInterrupt:
        ...


if __name__ == "__main__":
    main()
