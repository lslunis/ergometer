#!/usr/bin/env bash
set -euxo pipefail

gcloud compute --project=ergometer-1535902224242 instances create ergometer --zone=us-central1-a --machine-type=f1-micro --network-tier=STANDARD --no-service-account --no-scopes --tags=http-server,https-server --image=cos-81-12871-181-0 --image-project=cos-cloud --boot-disk-size=10GB --boot-disk-type=pd-standard --boot-disk-device-name=ergometer --address=ergometer

gcloud compute --project=ergometer-1535902224242 firewall-rules create default-allow-http --allow=tcp:80 --target-tags=http-server

gcloud compute --project=ergometer-1535902224242 firewall-rules create default-allow-https --allow=tcp:443 --target-tags=https-server
