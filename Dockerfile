FROM debian:latest
RUN apt-get update
RUN apt-get install -y python3 python3-pip python3-venv

WORKDIR /var/ergometer

COPY dev.py requirements.txt ergometer/
RUN python3 ergometer/dev.py build

COPY . ergometer
CMD [ "ergometer/venv/bin/python3", "-m", "ergometer.server_main", "data", "8080" ]

