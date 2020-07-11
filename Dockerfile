FROM debian:latest
RUN apt-get update
RUN apt-get install -y python3 python3-pip python3-venv

WORKDIR /var/ergometer

COPY do.py requirements_cli.txt ./
RUN ./do.py build server

COPY . .
CMD [ "./do.py", "run", "server" ]
