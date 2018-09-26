#!/usr/bin/env python

from collections import OrderedDict
from itertools import zip_longest
import json
import os
import re
from subprocess import check_output, CalledProcessError
import sys
from zipfile import ZipFile


def sh(command, v=False):
    if v:
        print(command)
    return check_output(command, text=True).strip()


def parse_version(v):
    return [int(s) for s in v.split(".")]


def dereference(link):
    try:
        return sh(f"git rev-parse --verify -q {link}^0")
    except CalledProcessError:
        return ""


version_string = sys.argv[1]
prefixed_version = f"v{version_string}"
version = parse_version(version_string)
os.chdir(os.path.dirname(os.path.realpath(__file__)))

assert not sh("git status --porcelain")
assert sh("git branch") == "* master"

with open("manifest.json") as f:
    manifest = json.load(f, object_pairs_hook=OrderedDict)
manifest_version = parse_version(manifest["version"])
if version != manifest_version:
    delta = list(
        vs[0] - vs[1]
        for vs in zip_longest(version, manifest_version, fillvalue=0)
    )
    increment = delta.index(1)
    assert all(i == 0 for i in delta[0:increment])
    assert all(i <= 0 for i in delta[increment + 1 :])
    manifest["version"] = version_string
    with open("manifest.json", "w", newline="\n") as f:
        json.dump(manifest, f, indent=2)
        print("", file=f)
    sh(f"git commit -a -m {prefixed_version}", v=True)

tag_commit = dereference(prefixed_version)
if tag_commit:
    assert tag_commit == dereference("HEAD")
else:
    sh(f"git tag {prefixed_version} -m {prefixed_version}", v=True)

sh("git merge-base --is-ancestor origin/master master")

if dereference("master") != dereference("origin/master"):
    sh("git push --follow-tags", v=True)

files = ["manifest.json", "config.js"]
for file in sh("git ls-files").splitlines():
    m = lambda p: re.search(p, file)
    if m(r"\.(html|js)$") and not m(r"\btest\b"):
        files.append(file)

with ZipFile("ergometer.zip", "w") as zip:
    for file in files:
        print(f"zipping {file}")
        zip.write(file)
