# Event Management Automation

Event Management Automation keeps two public Google Calendars up to date:

- selected Pokémon GO events;
- selected VALORANT Champions Tour fixtures.

The application fetches public event data, validates and normalises it, applies the filters in
[`config/feeds.yml`](config/feeds.yml), and reconciles the result with Google Calendar. It runs
automatically through GitHub Actions, uses Europe/London-aware date handling, and only modifies
events that it owns.

## Add the calendars

You do not need to run this project to use the calendars:

- [Add the VALORANT VCT Fixture Calendar](https://calendar.google.com/calendar/u/0?cid=ODcxY2FkZjc5MDA0ZTM3OWZjODYzMGNiY2Y2OWI3NWQwNTBlYjhhNTgxYjcxZmRkZDAyZWQzYTFmNGY2OTAzNEBncm91cC5jYWxlbmRhci5nb29nbGUuY29t)
- [Add the Pokémon GO Events Calendar](https://calendar.google.com/calendar/u/0?cid=MWM1NjVkMjRjMmJlZmUxYWRlNzkwMzdiYzA4NWFiM2I3MmZjMTg2MGNjNDYzZjY1NDdkMmU1ODUyNTNlMjZjZkBncm91cC5jYWxlbmRhci5nb29nbGUuY29t)

Google will ask which account should subscribe to the calendar. Once added, updates made by this
project appear automatically.

## How it works

1. The Pokémon source reads ScrapedDuck's event feed. The configured event-type whitelist is
   applied before each event is converted into either a timed or one-day all-day calendar event.
2. The VALORANT source requests upcoming fixtures from the `vlresports` API. If that provider is
   unavailable or invalid, VLRdevAPI reads the public VLR.gg match listing as a fallback.
3. Both feeds are converted to the same internal event model. Timezone-less Pokémon timestamps are
   interpreted as Europe/London wall times; timezone-aware timestamps are treated as absolute
   instants.
4. Each Google event receives private ownership metadata containing the feed and stable upstream
   identifier.
5. A reconciliation run compares desired events with owned Google events and calculates creates,
   full updates, deletions, and unchanged events. Manual or unrelated events are never selected.
6. Safety limits stop unexpectedly large deletions. A source failure never causes its calendar to
   be emptied.

The application is stateless: Google Calendar is the destination state, and no production JSON
cache or continuously running server is required.

## Data sources and credits

This project would not exist without the people maintaining the underlying community data sources:

- [ScrapedDuck by bigfoott](https://github.com/bigfoott/ScrapedDuck) provides the Pokémon GO event
  data collected from [Leek Duck](https://leekduck.com/).
- [vlresports by Orloxx23](https://github.com/Orloxx23/vlresports) provides the primary VALORANT
  matches API hosted at [vlr.orlandomm.net](https://vlr.orlandomm.net/docs).
- [VLRdevAPI by Vanshbordia](https://github.com/Vanshbordia/vlrdevapi) provides the fallback client
  for public [VLR.gg](https://www.vlr.gg/) match data.
- [Google Calendar API](https://developers.google.com/workspace/calendar/api/guides/overview)
  provides the calendar integration.

Huge credit and thanks to their creators and maintainers. Pokémon, Pokémon GO, VALORANT, Riot Games,
VLR.gg, Leek Duck, and Google are owned by their respective rights holders. This personal project
is not affiliated with or endorsed by them.

## Repository layout

```text
config/feeds.yml                 Version-controlled filters and behaviour
docs/CONFIGURATION.md            Complete configuration reference and change recipes
docs/AUTOMATION.md               GitHub Actions, Google authentication and operations guide
src/calendar_sync/               Application package
tests/                           Unit and regression tests
.github/workflows/ci.yml         Pull-request and main-branch quality checks
.github/workflows/sync.yml       Scheduled, post-merge and manual calendar sync
.github/workflows/migrate.yml    Protected one-time v1 migration and rollback backup
```

## Local development

Python 3.12 and [uv](https://docs.astral.sh/uv/) are required.

```powershell
uv sync --all-extras --locked
Copy-Item .env.example .env
```

Fill in the two calendar IDs and local Google credential path in `.env`, then run:

```powershell
uv run calendar-sync validate-config
uv run calendar-sync source-smoke --feed all
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run calendar-sync sync --feed all --dry-run
```

The final command reads the real sources and calendars but does not write anything. Review its
counts before running a live sync:

```powershell
uv run calendar-sync sync --feed all
```

`.env` and credential JSON files are intentionally ignored by Git and must never be committed.
GitHub Actions authenticates without a JSON key by using Google Workload Identity Federation.

## Making changes

Start with the guide that matches the change:

- [Configuration guide](docs/CONFIGURATION.md): Pokémon event types, timed/all-day behaviour,
  VALORANT patterns, timezone, colours, deletion limits, environment variables, and common edits.
- [Automation and operations guide](docs/AUTOMATION.md): CI/CD triggers, GitHub variables and
  environments, Workload Identity Federation, manual runs, deployment, migration, rollback, and
  troubleshooting.

For every behavioural change:

1. edit `config/feeds.yml` or the relevant source code;
2. add or update a regression test;
3. run the local quality commands above;
4. run a dry sync and review creates, updates, and deletions;
5. open a pull request and wait for CI;
6. merge only when the reported calendar changes are expected.

Production syncs run at 03:17 and 15:17 Europe/London and after successful CI on `main`, provided
the repository variable `CALENDAR_SYNC_ENABLED` is set to `true`.
