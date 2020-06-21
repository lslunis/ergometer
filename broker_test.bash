#!/bin/bash

# TODO: move to dev.py

mkdir -p test-data/{client-1,client-2,server}

ergometer/venv/bin/python -m ergometer.client_main `pwd`/test-data/client-1/ ws://localhost:8080 &
ergometer/venv/bin/python -m ergometer.client_main `pwd`/test-data/client-2/ ws://localhost:8080 &

ergometer/venv/bin/python -m ergometer.server_main `pwd`/test-data/server/ 8080 &
