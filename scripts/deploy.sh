#!/usr/bin/env bash
# Deploy new pipeline code without killing a running job.
#
#   scripts/deploy.sh local    # dw-local (make deploy)
#   scripts/deploy.sh prod     # dw-orchestration on the server
#
# 1. Build the new image while the current one keeps running.
# 2. Validate that the new definitions load; abort if not (old code stays up).
# 3. Wait until no run is in progress (DEPLOY_WAIT_TIMEOUT, default 1800s).
# 4. Recreate webserver + daemon. Queued runs stay queued and start afterwards.
#
# Platform services (postgres, clickhouse, metabase) are never touched.
set -euo pipefail

cd "$(dirname "$0")/.."

target="${1:-local}"
case "$target" in
  local)
    COMPOSE=(docker compose -p dw-local -f platform/compose.yaml -f compose.yaml --project-directory .)
    ;;
  prod)
    COMPOSE=(docker compose --project-directory . -f compose.prod.yaml --env-file .env)
    ;;
  *)
    echo "usage: $0 [local|prod]" >&2
    exit 2
    ;;
esac

timeout="${DEPLOY_WAIT_TIMEOUT:-1800}"
SERVICES=(dagster-webserver dagster-daemon)

# One-off containers from the NEW image, without the entrypoint (no migrations yet).
run_new() {
  "${COMPOSE[@]}" run --rm --no-deps -T --entrypoint "" dagster-webserver "$@"
}

echo "==> Building image"
"${COMPOSE[@]}" build dagster-webserver

echo "==> Validating definitions in the new image"
run_new dagster definitions validate -w workspace.yaml

echo "==> Waiting for in-progress runs (timeout ${timeout}s)"
if ! run_new python dagster_ops.py wait-idle --timeout "$timeout"; then
  echo "Aborting deploy: a run is still in progress. Nothing was restarted." >&2
  echo "Retry later, or raise DEPLOY_WAIT_TIMEOUT." >&2
  exit 1
fi

echo "==> Restarting ${SERVICES[*]}"
"${COMPOSE[@]}" up -d --no-deps "${SERVICES[@]}"

echo "==> Waiting for the webserver"
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T dagster-webserver \
      python -c "import urllib.request; urllib.request.urlopen('http://localhost:3000/server_info', timeout=3)" \
      >/dev/null 2>&1; then
    echo "Deploy complete."
    exit 0
  fi
  sleep 2
done

echo "Webserver did not come back within 120s. Check: ${COMPOSE[*]} logs dagster-webserver" >&2
exit 1
