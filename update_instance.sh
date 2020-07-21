#!/usr/bin/env bash
set -euxo pipefail

host=$(ls htpasswd)
ssh $host mkdir -p ergometer
rsync -Rv $(git ls-files) htpasswd/* $host:ergometer/
ssh $host bash ergometer/daemonize.sh
