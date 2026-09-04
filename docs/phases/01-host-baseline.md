# Phase 1 — Host baseline

**Status:** local loopback binds `local_done`; Ubuntu disk/UFW/nginx `not_started`. Tracker: [STATUS.md](../STATUS.md).

Goal: a hardened Ubuntu 24.04 box where the firewall actually means something.

## 1.1 Disk layout (before Docker)

```
/                 60 GB    OS
/var/lib/docker   60 GB    images and layers
/srv/dw           rest     data, bind-mounted into containers
```

Under `/srv/dw`: `clickhouse/`, `postgres/`, `metabase/`, `archive/`, `backups/`, `platform/`, `orchestration/`.

Local stand-in: Docker named volumes (`postgres_data`, `clickhouse_data`, `archive_data`). Production uses `/srv/dw` bind mounts.

## 1.2 OS

```bash
timedatectl set-timezone America/Argentina/Cordoba
apt install -y unattended-upgrades chrony
```

Store every timestamp in ClickHouse as UTC. Convert for display in Metabase.

SSH: key-only, no root login, no password auth.

## 1.3 Docker

Official Docker repo, not the Ubuntu package. `daemon.json` log rotation (`max-size: 50m`, `max-file: 3`) is not optional.

`docker` group membership is root-equivalent. Deploy user only; record it in the governance doc.

## 1.4 Firewall

```bash
ufw default deny incoming
ufw allow from <admin_subnet> to any port 22 proto tcp
ufw allow from <lan_subnet>   to any port 443 proto tcp
ufw enable
```

Hard invariant: no container publishes a port to `0.0.0.0`. Check before every go-live:

```bash
docker ps --format '{{.Names}}\t{{.Ports}}' | grep -v '127.0.0.1'
```

Local: Metabase `127.0.0.1:3000`, Dagster `127.0.0.1:3030`, ClickHouse `127.0.0.1:8123`. Postgres unpublished.

## 1.5 nginx on the host

Production only. Proxy `:443` → `127.0.0.1:3000` (Metabase). Dagster is SSH tunnel only: `ssh -L 3030:127.0.0.1:3030 user@dw`.

Deliverable: server reachable on 443 with a valid internal cert, placeholder page, firewall verified from outside the allowed subnet.

## How to check (local)

```bash
docker compose -f platform/compose.yaml -f compose.yaml --project-directory . \
  ps --format '{{.Names}}\t{{.Ports}}'
```

Every published port should show `127.0.0.1`.
