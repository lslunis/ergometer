FROM debian:latest
RUN apt-get update
RUN apt-get install -y python3 python3-pip python3-venv

WORKDIR /var/ergometer

COPY dev.py requirements.txt ./
RUN python3 dev.py build

COPY . .
CMD [ "venv/bin/python3", "ergometer_server.py" ]
