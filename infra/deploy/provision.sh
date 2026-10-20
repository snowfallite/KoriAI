#!/usr/bin/env bash
# One-time setup of the test VPS (tech.md §15.1, §20.2, S1-13); a rerun changes nothing.
# Run as root: sudo bash provision.sh <domain> "<deploy public key>"
# Installs Docker, rotates container logs, adds swap, creates the kori-deploy user and /opt/kori
# with .env and postgres.env. The secrets are generated here and never printed: read them on
# the server, and put real API keys into /opt/kori/.env by hand.
set -euo pipefail

domain=${1:?usage: provision.sh <domain> "<deploy public key>"}
deploy_key=${2:?usage: provision.sh <domain> "<deploy public key>"}
# shellcheck source=/dev/null
. /etc/os-release
# GitHub masks secret values in logs: a rare user name (VPS_USER) keeps them readable.
user=kori-deploy

if ! command -v docker >/dev/null; then
  apt-get update -q
  apt-get install -yq ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc]" \
    "https://download.docker.com/linux/$ID $VERSION_CODENAME stable" \
    >/etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -yq docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

# json-file logs grow without bound unless they rotate.
daemon='{"log-driver": "json-file", "log-opts": {"max-size": "10m", "max-file": "3"}}'
if [[ "$(cat /etc/docker/daemon.json 2>/dev/null)" != "$daemon" ]]; then
  echo "$daemon" >/etc/docker/daemon.json
  systemctl restart docker
fi

# Swap absorbs short peaks: a deploy migrates next to the live API, Firefox starts on demand.
if [[ ! -e /swapfile ]]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi
swapon --show | grep -q /swapfile || swapon /swapfile
echo 'vm.swappiness = 10' >/etc/sysctl.d/90-kori.conf
sysctl -q -p /etc/sysctl.d/90-kori.conf

# The user runs compose for GitHub Actions. The docker group equals root, so its key gets
# no forwarding and no terminal.
id "$user" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash --groups docker "$user"
install -d -m 700 -o "$user" -g "$user" "/home/$user/.ssh"
install -m 600 -o "$user" -g "$user" /dev/null "/home/$user/.ssh/authorized_keys"
echo "restrict $deploy_key" >"/home/$user/.ssh/authorized_keys"
install -d -m 750 -o "$user" -g "$user" /opt/kori

cd /opt/kori
if [[ ! -e .env ]]; then
  db_password=$(openssl rand -hex 24)
  umask 077
  cat >.env <<EOF
# Test VPS (S1-13, tech.md §15.3). The API refuses unknown keys.
# Real clients run where the keys exist (L-02, L-05, L-07): fill a key, flip its *_MODE.
APP_ENV=staging
APP_BASE_URL=https://$domain
APP_ALLOWED_ORIGINS=https://$domain
DATABASE_URL=postgresql+psycopg://app:$db_password@postgres:5432/app
QDRANT_URL=http://qdrant:6333
VECTORS_MODE=qdrant
COOKIE_SECURE=true
REGISTRATION_MODE=invite
SEED_OWNER_PASSWORD=$(openssl rand -hex 12)
TINVEST_TOKEN_KEYS=k1:$(openssl rand -base64 32)
TINVEST_TOKEN_ACTIVE_KEY=k1
# Until F-01 the demo user holds only the made-up seed token, so T-Invest stays fake.
TINVEST_MODE=fake
TINVEST_SYSTEM_TOKEN=
LLM_MODE=fake
GIGACHAT_CREDENTIALS=
WEB_MODE=fake
TAVILY_API_KEY=
DISCLOSURE_MODE=real
EMBEDDINGS_MODE=real
FETCH_MODE=real
EOF
  echo "POSTGRES_PASSWORD=$db_password" >postgres.env
  # The API runs as uid 10001 and reads .env itself; compose reads both files as $user.
  chown "10001:$user" .env
  chmod 640 .env
  chown "$user:$user" postgres.env
fi
echo "provision: done"
