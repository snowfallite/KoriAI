#!/usr/bin/env bash
# Ships one image tag on the test VPS (tech.md §20.2). deploy.yml copies this file next to
# docker-compose.yml in /opt/kori and runs it as kori-deploy with the GHCR read token on
# stdin. A tag that fails /api/health/ready for 90 s gives way to the tag in .deployed_sha.
# By hand, with the images already pulled: bash deploy.sh <sha-tag> <registry user> </dev/null
set -euo pipefail

tag=${1:?usage: deploy.sh <sha-tag> <registry user>}
user=${2:?usage: deploy.sh <sha-tag> <registry user>}
cd "$(dirname "$0")"
previous=$(cat .deployed_sha 2>/dev/null || true)

# The login lasts for the pull only: a rollback uses the images already on disk.
if [[ ! -t 0 ]] && read -r token && [[ -n $token ]]; then
  docker login ghcr.io --username "$user" --password-stdin <<<"$token" >/dev/null
  trap 'docker logout ghcr.io >/dev/null' EXIT
fi

export KORI_TAG=$tag
docker compose pull --quiet
# Migrations only expand the schema (§5.7): the running version keeps working meanwhile.
docker compose run --rm api alembic upgrade head

# The egress to Tavily (§15.1): nodes from the owner's subscription, an empty list without one.
# A broken subscription keeps the nodes xray has; the script says why. deploy.yml ships
# base.json and the script.
python3 xray/xray_nodes.py xray/subscription xray/nodes.json || true
[[ -f xray/nodes.json ]] || printf '{"outbounds": []}\n' >xray/nodes.json
xray_config=$(cat xray/base.json xray/nodes.json | sha256sum)

docker compose up -d --remove-orphans
# xray reads its config once at start, and up -d leaves a running xray alone.
if [[ $xray_config != "$(cat xray/.applied 2>/dev/null)" ]]; then
  docker compose restart xray
  echo "$xray_config" >xray/.applied
fi

ready() {
  local url=http://127.0.0.1:8000/api/health/ready
  docker compose exec -T api python -c "import urllib.request as r; r.urlopen('$url', timeout=5)" \
    >/dev/null 2>&1
}

wait_ready() {
  local deadline=$((SECONDS + 90))
  until ready; do
    ((SECONDS < deadline)) || return 1
    sleep 2
  done
}

if ! wait_ready; then
  echo "deploy: $tag is not ready after 90 s" >&2
  docker compose logs --tail 80 api >&2 || true
  if [[ -n $previous ]]; then
    KORI_TAG=$previous docker compose up -d --remove-orphans
    if wait_ready; then
      echo "deploy: rolled back to $previous" >&2
    else
      echo "deploy: rolled back to $previous, but it is not ready either" >&2
    fi
  fi
  exit 1
fi

echo "$tag" >.deployed_sha
# Keep the live tag and the rollback tag: older images only eat the disk.
docker image ls --format '{{.Repository}}:{{.Tag}}' \
  | grep -E '/kori-(api|caddy):sha-' \
  | grep -vE ":(${tag}|${previous:-none})\$" \
  | xargs -r docker image rm >/dev/null || true
docker image prune --force >/dev/null
echo "deploy: $tag is live"
