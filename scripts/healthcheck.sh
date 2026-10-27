#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "Local HTTP health"
curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8095/health
echo
echo "Running containers"
docker compose ps
echo "Recent logs (secrets may be present; do not paste unredacted publicly)"
docker compose logs --tail 25 web scheduler
