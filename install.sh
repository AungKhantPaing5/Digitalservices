#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
command -v docker >/dev/null || { echo 'Install Docker Engine + Compose plugin first: https://docs.docker.com/engine/install/ubuntu/';exit 1; }
docker compose version >/dev/null
if [ ! -f .env ];then
  cp .env.example .env
  secret=$(python3 -c 'import secrets;print(secrets.token_hex(48))')
  sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$secret/" .env
  chmod 600 .env
  echo 'Created .env. REQUIRED: change ADMIN_EMAIL and ADMIN_PASSWORD, payment numbers, Telegram credentials.'
  echo 'Edit .env, then run bash install.sh again.'
  exit 0
fi
if grep -Eq '^ADMIN_PASSWORD=(CHANGE_ME[^[:space:]]*|$)|^ADMIN_EMAIL=admin@yourdomain.com|^SECRET_KEY=GENERATED_BY_INSTALLER' .env;then
 echo 'Refusing to start with default admin credentials. Edit .env first.';exit 1
fi
mkdir -p data/proofs
chmod 700 data
chown -R 10001:10001 data
docker compose build
docker compose up -d web scheduler
if grep -Eq '^TUNNEL_TOKEN=.{20,}' .env;then docker compose --profile tunnel up -d tunnel;fi
echo 'DigitalServices started at http://127.0.0.1:8095 (local only).'
echo 'For HTTPS configure Cloudflare Tunnel public hostname to http://web:8000.'
