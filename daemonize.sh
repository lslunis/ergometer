#!/usr/bin/env bash
set -euxo pipefail

cd ~/ergometer
docker build -t ergometer_server .

host=$(ls htpasswd)
running() {
    [[ -n "$(docker ps -a --format '{{.Names}}' --filter name="$1")" ]]
}

if running ergometer_server; then
    docker stop ergometer_server
    docker rm ergometer_server
fi
docker run --detach --restart always -e LETSENCRYPT_HOST=$host -e VIRTUAL_HOST=$host -e VIRTUAL_PORT=5187 -p 5187:5187 --name ergometer_server ergometer_server

if ! running nginx; then
    docker run --detach --restart always -p 80:80 -p 443:443 -v htpasswd:/etc/nginx/htpasswd -v /etc/nginx/certs -v /etc/nginx/vhost.d -v /usr/share/nginx/html -v /var/run/docker.sock:/tmp/docker.sock:ro --name nginx jwilder/nginx-proxy
fi

if ! running certs; then
    docker run --detach --restart always --volumes-from nginx -v /var/run/docker.sock:/var/run/docker.sock:ro -e DEFAULT_EMAIL=ls@lunis.net --name certs jrcs/letsencrypt-nginx-proxy-companion
fi
