#!/usr/bin/env bash
# docker compose for the tag live on the VPS: docker-compose.yml needs KORI_TAG for every
# command, .deployed_sha holds it. Example: sudo -u kori-deploy bash /opt/kori/compose.sh logs api
set -euo pipefail

cd "$(dirname "$0")"
KORI_TAG=$(cat .deployed_sha) exec docker compose "$@"
