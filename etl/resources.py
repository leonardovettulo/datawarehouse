from dagster import ConfigurableResource, EnvVar


class SourceDBResource(ConfigurableResource):
    host: str
    port: str
    dbname: str
    user: str
    password: str

    def connect(self):
        import psycopg

        return psycopg.connect(
            host=self.host,
            port=int(self.port),
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            options="-c TimeZone=UTC",
        )


class ClickHouseResource(ConfigurableResource):
    host: str
    port: str
    user: str
    password: str

    def client(self):
        import clickhouse_connect

        return clickhouse_connect.get_client(
            host=self.host,
            port=int(self.port),
            username=self.user,
            password=self.password,
            connect_timeout=10,
        )


class ArchiveResource(ConfigurableResource):
    root: str


def default_source() -> SourceDBResource:
    return SourceDBResource(
        host=EnvVar("SOURCE_PG_HOST"),
        port=EnvVar("SOURCE_PG_PORT"),
        dbname=EnvVar("SOURCE_PG_DB"),
        user=EnvVar("SOURCE_PG_USER"),
        password=EnvVar("PG_SOURCE_PASSWORD"),
    )


def default_clickhouse() -> ClickHouseResource:
    return ClickHouseResource(
        host=EnvVar("CLICKHOUSE_HOST"),
        port=EnvVar("CLICKHOUSE_PORT"),
        user=EnvVar("CLICKHOUSE_USER"),
        password=EnvVar("CH_DAGSTER_PASSWORD"),
    )


def default_archive() -> ArchiveResource:
    return ArchiveResource(root=EnvVar("ARCHIVE_ROOT"))
