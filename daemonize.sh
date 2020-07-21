#!/usr/bin/env bash
set -euxo pipefail

cd ~/ergometer
host=$(ls htpasswd)
docker build -t ergometer_server .

docker run --detach --restart always -e LETSENCRYPT_HOST=$host -e VIRTUAL_HOST=$host -e VIRTUAL_PORT=5187 -p 5187:5187 ergometer_server

docker run --detach --restart always -p 80:80 -p 443:443 -v htpasswd:/etc/nginx/htpasswd -v /etc/nginx/certs -v /etc/nginx/vhost.d -v /usr/share/nginx/html -v /var/run/docker.sock:/tmp/docker.sock:ro jwilder/nginx-proxy

docker run --detach --restart always --volumes-from nginx-proxy -v /var/run/docker.sock:/var/run/docker.sock:ro -e DEFAULT_EMAIL=ls@lunis.net jrcs/letsencrypt-nginx-proxy-companion
