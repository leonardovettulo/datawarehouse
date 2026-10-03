#!/usr/bin/env bash
# Host health check for the DW server. Runs every 5 minutes (dw-healthcheck.timer)
# and reports to a heartbeat monitor (Better Stack, Healthchecks.io, ...):
#
#   all good  → POST $HOST_HEARTBEAT_URL        (body: summary)
#   problems  → POST $HOST_HEARTBEAT_URL/fail   (body: what is wrong)
#   box down  → no ping at all; the monitor alerts when the period lapses
#
# Only host facts leave the box (disk %, container states). Never data.
# Config: /etc/dw/healthcheck.env (override path with DW_HEALTHCHECK_ENV).
set -uo pipefail

conf="${DW_HEALTHCHECK_ENV:-/etc/dw/healthcheck.env}"
# shellcheck disable=SC1090
[ -f "$conf" ] && . "$conf"

HOST_HEARTBEAT_URL="${HOST_HEARTBEAT_URL:-}"
DISK_PATHS="${DW_DISK_PATHS:-/srv/dw /}"
DISK_MAX_PCT="${DW_DISK_MAX_PCT:-80}"
MEM_MIN_AVAILABLE_PCT="${DW_MEM_MIN_AVAILABLE_PCT:-10}"
COMPOSE_PROJECTS="${DW_COMPOSE_PROJECTS:-dw-platform dw-orchestration}"
EXPECTED_SERVICES="${DW_EXPECTED_SERVICES:-postgres clickhouse metabase dagster-webserver dagster-daemon}"

problems=()
facts=()

# --- disk: one full disk takes down ClickHouse, Postgres and Metabase together ---
for path in $DISK_PATHS; do
  if [ ! -e "$path" ]; then
    problems+=("disk: $path does not exist")
    continue
  fi
  pct=$(df -P "$path" | awk 'NR == 2 { gsub("%", "", $5); print $5 }')
  facts+=("disk $path ${pct}%")
  if [ "$pct" -ge "$DISK_MAX_PCT" ]; then
    problems+=("disk: $path at ${pct}% (limit ${DISK_MAX_PCT}%)")
  fi
done

# --- memory (Linux only) ---
if [ -r /proc/meminfo ]; then
  avail_pct=$(awk '/^MemTotal:/ { t = $2 } /^MemAvailable:/ { a = $2 } END { printf "%d", a * 100 / t }' /proc/meminfo)
  facts+=("mem available ${avail_pct}%")
  if [ "$avail_pct" -lt "$MEM_MIN_AVAILABLE_PCT" ]; then
    problems+=("memory: only ${avail_pct}% available (limit ${MEM_MIN_AVAILABLE_PCT}%)")
  fi
fi

# --- containers: every expected compose service exists, runs, and is not unhealthy ---
if ! docker info >/dev/null 2>&1; then
  problems+=("docker: daemon not reachable")
else
  for service in $EXPECTED_SERVICES; do
    ids=""
    for project in $COMPOSE_PROJECTS; do
      ids+=" $(docker ps -aq \
        --filter "label=com.docker.compose.project=$project" \
        --filter "label=com.docker.compose.service=$service")"
    done
    ids=$(echo "$ids" | xargs)
    if [ -z "$ids" ]; then
      problems+=("container: $service not found")
      continue
    fi
    for id in $ids; do
      read -r status health < <(docker inspect -f \
        '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$id")
      if [ "$status" != "running" ]; then
        problems+=("container: $service is $status")
      elif [ "$health" = "unhealthy" ]; then
        problems+=("container: $service is unhealthy")
      fi
    done
  done
  facts+=("containers checked: $EXPECTED_SERVICES")
fi

host=$(hostname)
if [ "${#problems[@]}" -gt 0 ]; then
  report="$host: ${#problems[@]} problem(s)"$'\n'"$(printf '%s\n' "${problems[@]}")"
  url="${HOST_HEARTBEAT_URL%/}/fail"
  rc=1
else
  report="$host: ok"$'\n'"$(printf '%s\n' "${facts[@]}")"
  url="${HOST_HEARTBEAT_URL%/}"
  rc=0
fi

echo "$report"

if [ -z "$HOST_HEARTBEAT_URL" ]; then
  echo "HOST_HEARTBEAT_URL is not set; result not reported." >&2
  exit "$rc"
fi

if ! curl -fsS -m 15 --retry 3 --data-raw "$report" "$url" >/dev/null; then
  echo "Could not reach heartbeat URL." >&2
  exit 2
fi
exit "$rc"
