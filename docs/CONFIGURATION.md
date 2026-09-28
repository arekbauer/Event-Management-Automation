# Configuration guide

This guide documents every supported setting and the safest process for changing calendar content.
The application validates configuration before it contacts a source or Google Calendar. Unknown
keys, invalid values, and inconsistent all-day settings fail immediately.

## Configuration locations

Configuration is split by responsibility:

| Location | Contains | Committed |
| --- | --- | --- |
| `config/feeds.yml` | Shared product behaviour, filters and safety limits | Yes |
| `.env` | Local calendar IDs, credential path and optional webhook | No |
| GitHub repository variables | Production calendar IDs and Google identity values | Stored in GitHub |
| GitHub environment secrets | Optional production Discord webhook | Stored in GitHub |

The CLI loads `.env` automatically. A variable already set in the shell takes precedence over the
same variable in `.env`.

## Top-level settings

```yaml
version: 3
timezone: Europe/London
```

- `version` identifies the supported configuration schema. Change it only alongside a code change
  that explicitly supports the new schema.
- `timezone` must be an IANA timezone name. It controls interpretation of timezone-less Pokémon
  timestamps, all-day boundaries and Google Calendar display metadata. Do not replace it with a
  fixed UTC offset; Europe/London changes offset during daylight-saving time.

## Deletion safety

```yaml
safety:
  max_deletions: 25
  max_deletion_fraction: 0.50
```

A sync is rejected when either limit is exceeded:

- `max_deletions` is the largest absolute number of owned events that one feed may delete.
- `max_deletion_fraction` is the largest fraction of currently owned feed events that may be
  deleted in one run.

An empty desired set is always considered unsafe when it would delete existing events. Manual
workflow runs expose `allow_unsafe_deletes`, but that override should only be used after reviewing a
dry run and confirming the source and filter change are correct.

## Pokémon GO feed

```yaml
pokemon_go:
  enabled: true
  calendar_id_env: POKEMON_GO_CALENDAR_ID
  source_url: https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json
  color_id: "3"
  future_start_only: true
  include_event_types: []
  all_day_event_types: []
```

### Fields

- `enabled`: when `false`, the feed is unavailable to `sync` and `source-smoke`.
- `calendar_id_env`: name of the environment variable containing the destination calendar ID.
- `source_url`: ScrapedDuck JSON endpoint.
- `color_id`: Google Calendar event colour ID, kept as a quoted string.
- `future_start_only`: when `true`, events starting today or earlier in Europe/London are excluded,
  even if their source end time is later. This preserves the v1 calendar behaviour.
- `include_event_types`: exact, case-sensitive ScrapedDuck `eventType` values to include.
- `all_day_event_types`: included types that should appear as a one-day all-day event on their
  local start date. The source end time is intentionally ignored for these types.

Every value in `all_day_event_types` must also exist in `include_event_types`; validation rejects an
inconsistent configuration.

Types not listed as all-day retain their source start and end times. For example, `raid-hour` and
`community-day` are timed events. Google all-day end dates are exclusive, so an event displayed on
2026-10-07 is sent as start `2026-10-07`, end `2026-10-08`.

### Add a Pokémon event type

1. Confirm the exact `eventType` in the live ScrapedDuck payload.
2. Add it to `include_event_types`.
3. Add it to `all_day_event_types` only if it should occupy one all-day block on its start date.
4. Add or update a source test covering its desired time representation.
5. Validate and inspect the change:

   ```powershell
   uv run calendar-sync validate-config
   uv run calendar-sync source-smoke --feed pokemon_go
   uv run calendar-sync sync --feed pokemon_go --dry-run
   ```

### Remove a Pokémon event type

Remove it from both lists, validate, and run a dry sync. Existing v2-owned events of that type will
appear as deletions. If the deletion safety threshold blocks an expected change, use the manual
workflow override only after checking the complete deletion count.

### Change timed versus all-day behaviour

- Move a type into `all_day_event_types` to make it one all-day event on its start date.
- Remove a type from `all_day_event_types` to preserve its source times.

The reconciliation layer uses a full Google event update, so it can safely convert an existing
owned event between all-day and timed representations.

## VALORANT feed

```yaml
valorant:
  enabled: true
  calendar_id_env: VALORANT_CALENDAR_ID
  primary_url: https://vlr.orlandomm.net/api/v1/matches
  fallback_provider: vlrdevapi
  color_id: "6"
  include_patterns:
    - "*VCT 2026*"
  exclude_patterns: []
```

### Fields

- `primary_url`: primary `vlresports` matches endpoint. The client adds `theme=light` and requests
  JSON.
- `fallback_provider`: currently must be `vlrdevapi`.
- `include_patterns`: at least one case-insensitive shell-style glob must match.
- `exclude_patterns`: optional case-insensitive globs; exclusions always win.

Patterns are evaluated against one combined string containing the title, series, tournament and
description. `*` matches any number of characters and `?` matches one character.

### Change the VALORANT competitions

1. Add a narrow include pattern for the desired competition or season.
2. Use an exclude pattern for an unwanted stage or series that otherwise matches.
3. Run:

   ```powershell
   uv run calendar-sync source-smoke --feed valorant
   uv run calendar-sync sync --feed valorant --dry-run
   ```

4. Review both the desired count and proposed deletions before merging.

## Local environment variables

Create `.env` from the template:

```powershell
Copy-Item .env.example .env
```

```dotenv
POKEMON_GO_CALENDAR_ID=calendar-id@group.calendar.google.com
VALORANT_CALENDAR_ID=calendar-id@group.calendar.google.com
GOOGLE_APPLICATION_CREDENTIALS=C:\absolute\path\to\credentials.json
DISCORD_WEBHOOK_URL=
```

- Calendar IDs identify destinations and are not authentication secrets.
- `GOOGLE_APPLICATION_CREDENTIALS` is only for local authentication. GitHub uses keyless Workload
  Identity Federation.
- `DISCORD_WEBHOOK_URL` is optional and must be treated as a secret.

## Command reference

```powershell
# Validate YAML only
uv run calendar-sync validate-config

# Contact public sources without accessing Google
uv run calendar-sync source-smoke --feed all
uv run calendar-sync source-smoke --feed pokemon_go
uv run calendar-sync source-smoke --feed valorant

# Calculate Google changes without writing
uv run calendar-sync sync --feed all --dry-run

# Apply reconciliation
uv run calendar-sync sync --feed all
```

Available feed values are `all`, `pokemon_go`, and `valorant`.

## Safe change checklist

Before merging any configuration change:

1. `uv run calendar-sync validate-config`
2. `uv run calendar-sync source-smoke --feed all`
3. `uv run pytest`
4. `uv run ruff format --check .`
5. `uv run ruff check .`
6. `uv run mypy`
7. `uv run calendar-sync sync --feed all --dry-run`
8. Review creates, updates, deletions, rejected records, warnings and provider names.

Never make a filter broader and approve a destructive result based only on the total desired count;
inspect which events will change.
