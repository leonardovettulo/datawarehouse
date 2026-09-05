# Database secret rotation

Changing `.env` does **not** rotate database users. The Postgres and ClickHouse
scripts under `docker-entrypoint-initdb.d` run only when their data directory is
empty. On an existing installation, changing only `.env` makes clients use a
password the database does not know.

## Safe sequence

1. Schedule a short maintenance window and confirm the latest backup.
2. Change the password in the database using an existing administrator session.
3. Update the matching value in `.env` (mode `600`) and in the institution's
   password manager.
4. Recreate only the dependent services.
5. Verify Dagster and Metabase connectivity.

## Postgres

Open `psql` as the Postgres administrator and use its interactive password
command so the new secret is not copied into shell history:

```text
\password dagster
\password metabase
```

Then update `PG_DAGSTER_PASSWORD` / `PG_METABASE_PASSWORD` and restart the
Dagster or Metabase containers respectively.

## ClickHouse

Open `clickhouse-client` as `default` and rotate one application user at a time:

```sql
ALTER USER dagster IDENTIFIED WITH plaintext_password BY '<new secret>';
ALTER USER metabase IDENTIFIED WITH plaintext_password BY '<new secret>';
```

Update `CH_DAGSTER_PASSWORD` / `CH_METABASE_PASSWORD`, recreate the dependent
containers, and remove the statements from client history if the client records
them. Rotating `default` (`CH_ADMIN_PASSWORD`) follows the same process but must
be done last.

## Metabase saved ClickHouse credential

`CH_METABASE_PASSWORD` is also stored encrypted in the Metabase application
database. After rotating it in ClickHouse, update the **ClickHouse marts**
connection in Metabase. `scripts/setup_metabase.py` only creates a missing
connection; it intentionally does not overwrite an existing one.

Never use `make reset` to rotate production credentials: it destroys local
database state instead of changing an existing user's password.
