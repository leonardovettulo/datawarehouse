# Official image behaviour: https://clickhouse.com/docs/get-started/setup/self-managed/docker
# Scripts in /docker-entrypoint-initdb.d run once (empty data dir), alphabetically.
# Do not set CLICKHOUSE_SKIP_USER_SETUP — that makes `default` reachable without a password.
FROM clickhouse/clickhouse-server:24.8
COPY config.d /etc/clickhouse-server/config.d
COPY docker-entrypoint-initdb.d /docker-entrypoint-initdb.d
RUN chmod +x /docker-entrypoint-initdb.d/*.sh
