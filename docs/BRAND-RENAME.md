# Brand rename: FreakTown → FUNNIER

The product is **FUNNIER**: brand text, UI copy, docs, package scopes
(`@freaktown/*` → `@funnier/*`), Python modules and CLI names. The old
name stays only where changing it would break a deploy, stored data or
wire compatibility. That allow-list is below. The guard test
`packages/contracts/tests/brand-rename.test.ts` mirrors it and fails if
the old name shows up anywhere else, in file content or in file paths.

## Renamed paths

| old | new |
|---|---|
| `backend/services/freaktown/` (`__init__.py`, `bundle.py`, `cues.py`) | `backend/services/funnier/` |
| `freaktown` (launcher script) | `funnier` |
| `freaktown.py` | `funnier.py` |
| `freaktown_cli/terminal.py` | `funnier_cli/terminal.py` |
| `tests/unit/test_freaktown.py` | `tests/unit/test_funnier.py` |
| `@freaktown/contracts`, `/stage-runtime`, `/newsroom`, `/live` | `@funnier/…` |
| `freaktown.newsroom.*` / `freaktown.live.sets.*` contract ids | `funnier.newsroom.*` / `funnier.live.sets.*` |

## Allow-list (kept on purpose)

| kept | where | why |
|---|---|---|
| any URL containing the old name | deploy hostnames, `github.com/prx0r/freaktown`, `*.workers.dev` | Live DNS, tunnel routes and the real repo slug. Renaming means a DNS/infra migration. |
| server and repo paths | `prx0r/freaktown`, `/root/freaktown`, `/home/ubuntu/freaktown`, `/srv/…`, `/opt/…`, venv paths, `/workspace/work/freaktown` | where checkouts and venvs live on the boxes |
| `freaktown-trial`, `freaktown-perform` | the cloudflared tunnel and the perform worker | deployed Cloudflare resource names |
| R2 / D1 / worker name values | `r2://freaktown`, `"freaktown"`, `` `freaktown` `` | existing bucket, database and worker; a rename makes new empty ones |
| `freaktown-postgres` and Postgres DSNs | Hyperdrive config, DB and role names | the live database |
| `freaktown-dev-secret-change-in-prod`, `freaktown-guest`, `freaktown-creator` | dev secret, hash salts | Changing a salt changes every derived hash: guests and creators would lose their ids. |
| `freaktown-theme`, `freaktown-assets` | browser storage key, bucket option | users' saved theme; the asset bucket |
| `freak_town_ai`, `FREAK_TOWN_DRAW_V1` | persisted enum value, draw-algorithm id | stored in rows; the draw id makes old draws reproducible |
| `freaktown_id`, `freaktown_draft`, `freaktown_admin_key`, `freaktown_session_id` | client storage keys | Renaming them logs people out and drops drafts. |
| `FREAKTOWN_SOURCE` | migration pin | migrations already applied refer to it |
| `freaktown.service`, `deploy/*.service` | systemd unit (content and file name) | running units on the servers |
| `"service": "freaktown"` | health-check response | monitors match on it |
| `(?:freaktown\|FUNNIER)` | skin title matcher | still accepts the legacy title from boxes running older code |
| `freaktown.<contract>/vN` (except `newsroom.*`, `live.sets.*`) | sealed bundle and golden-fixture contract ids | These are wire ids already in sealed bundles. A new id means a new contract version. |

Binary assets (images, models, audio, video, fonts, archives) are skipped
by the guard.

## Adding to the list

1. Change the code first if you can. The allow-list is for things that
   can't change without a migration.
2. If it really has to stay, add a narrow regex to `ALLOW` in
   `brand-rename.test.ts` and a row here giving the reason. Keep the two
   in sync.
3. Retiring an entry (for example after a DNS move or a contract `v2`)
   means renaming it, removing its regex and removing its row.

## Downstream repos

`prx0r/damn` (Goodnight News studio adapter) emits
`funnier.newsroom.rundown/v1` from prx0r/damn#2. Merge it with or after
the freaktown PR that renames the newsroom contract.
