FROM clickhouse/clickhouse-server:24.8
COPY config.d /etc/clickhouse-server/config.d
COPY docker-entrypoint-initdb.d /docker-entrypoint-initdb.d
RUN chmod +x /docker-entrypoint-initdb.d/*.sh
