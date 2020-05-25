#!/bin/bash

# Not sure what the equivalent of this would be in windows.

# Make directories for data.
mkdir -p test-data/{client-1,client-2,server}

# Start clients.
python3 data_processor_main.py `pwd`/test-data/client-1/ ws://localhost:8080 &
python3 data_processor_main.py `pwd`/test-data/client-2/ ws://localhost:8080 &

# Start broker.
python3 broker.py `pwd`/test-data/server/ 8080 &