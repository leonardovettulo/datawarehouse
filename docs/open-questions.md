# Open questions

From the implementation plan. Update answers here; do not bury them in chat.

## Blocking before compose can be finalized for production

| # | Question | Answer |
|---|---|---|
| 1 | Server spec: cores, RAM, disk size and layout | _open_ — drives CH `mem_limit` |
| 2 | Does the log-shipped replica exist and work today? Restore interval? | _open_ |
| 3 | Rough volume: 20 GB or 2 TB? | _open_ — size from relevamiento |
| 4 | Backup destination: NAS, second server, or request one? | _open_ |
| 5 | Sudo on the box, or does IT run it? Can we set UFW and nginx? | _open_ |

## Needed before Phase 6–7 in production

| # | Question | Answer |
|---|---|---|
| 6 | Does the tablero need patient identifiers, or hash at marts? | Local hashes. Consejo confirmation _open_ |
| 7 | AD/LDAP for Metabase? | _open_ |
| 8 | Is Portada Salud in scope, same SQL Server or separate? | _open_ |
| 9 | Internal CA cert or self-signed? | _open_ |
| 10 | How many Metabase users, which areas? | _open_ |

