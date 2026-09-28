# Calendar Sync v2

Calendar Sync imports Pokémon GO events and Valorant fixtures into two Google calendars. It
runs as a stateless GitHub Actions job, normalises both feeds into one event model, and safely
reconciles only the Google events it owns.

## What changed in v2

- No PythonAnywhere host, local JSON cache, fixed UTC offset, or delete-and-recreate loop.
- Timezone-aware conversion with `zoneinfo` and an explicit `Europe/London` policy.
- Versioned filters in [`config/feeds.yml`](config/feeds.yml).
- Stable event ownership through private Google Calendar extended properties.
- The OrlandoMM Valorant API with direct VLR parsing through `vlrdevapi` as a fallback, plus
  retries and response validation.
- Pull-request CI, twice-daily production runs, merge-to-main delivery, dry runs, deletion
  safeguards, Discord failure alerts, and a reversible v1 migration.
- Keyless Google authentication from GitHub through Workload Identity Federation.

## Development

Python 3.12 and [uv](https://docs.astral.sh/uv/) are required.

### First local run

1. Install the project and its development tools:

   ```powershell
   uv sync --all-extras --locked
   ```

2. Copy `.env.example` to `.env` and replace both example calendar IDs. For local service-account
   authentication, set `GOOGLE_APPLICATION_CREDENTIALS` to the absolute path of the JSON key.
   `.env` and credential JSON files are ignored by Git and must never be committed.

   ```powershell
   Copy-Item .env.example .env
   ```

3. Validate the YAML and test the public sources without accessing Google:

   ```powershell
   uv run calendar-sync validate-config
   uv run calendar-sync source-smoke --feed all
   ```

4. Run all local quality checks:

   ```powershell
   uv run ruff format --check .
   uv run ruff check .
   uv run mypy
   uv run pytest
   ```

5. Calculate the exact Google Calendar changes without writing anything:

   ```powershell
   uv run calendar-sync sync --feed all --dry-run
   ```

6. Only after the dry-run counts have been reviewed, perform a normal reconciliation:

   ```powershell
   uv run calendar-sync sync --feed all
   ```

The CLI loads `.env` automatically without replacing variables already set in the shell. A dry run
reads calendars and upstream feeds but performs no writes. During the v1-to-v2 cutover, use the
migration procedure below instead of step 6; a normal first sync would create v2 events alongside
the untagged v1 events.

## Filters and time handling

Configuration is validated before any source or calendar access.

- Pokémon `include_event_types` and `all_day_event_types` are exact event-type slugs.
- Valorant include and exclude rules are case-insensitive shell-style glob patterns over the
  tournament, series, title, and description. Exclusions win.
- A timestamp with `Z` or an offset is an absolute instant. A timezone-less Pokémon timestamp
  is a `Europe/London` wall time, with DST supplied by the IANA timezone database.
- Timed events are stored as UTC instants. Google receives the display timezone separately.
- Google all-day end dates are exclusive.

`config/feeds.yml` contains version-controlled product behaviour: source URLs, timezone, enabled
feeds, filters, colours, and deletion limits. `.env` contains deployment-specific values: calendar
IDs, the local credential path, and the optional Discord webhook. Changing YAML filters affects the
next dry run immediately; changing `.env` does not require reinstalling the project.

When changing filters, open a pull request and inspect the CI result. After merge, the successful
CI run triggers a production sync. Large removals are blocked by `safety` limits; inspect a dry run
before manually using `--allow-unsafe-deletes`.

## GitHub and Google setup

1. Revoke the legacy service-account JSON key and the old Discord webhook. Delete local copies
   after confirming they are no longer needed.
2. Enable the Google Calendar API and create or reuse a service account with no downloadable key.
3. Share both destination calendars with the service-account email and grant event editing access.
4. Create a Google Workload Identity Pool/provider for GitHub OIDC. Restrict its attribute
   condition to `assertion.repository == 'arekbauer/Event-Management-Automation' && assertion.ref ==
   'refs/heads/main'`, then grant that repository principal `roles/iam.workloadIdentityUser` on the
   service account.
5. Create a GitHub environment named `production` without required reviewers, so scheduled jobs
   can run unattended. Create `production-migration` with a required reviewer.
6. Add these repository variables:
   - `CALENDAR_SYNC_ENABLED` set to `false` until the v2 migration is complete
   - `GCP_PROJECT_ID`
   - `GCP_WORKLOAD_IDENTITY_PROVIDER` using the full `projects/.../providers/...` resource name
   - `GCP_SERVICE_ACCOUNT`
   - `POKEMON_GO_CALENDAR_ID`
   - `VALORANT_CALENDAR_ID`
7. Add the replacement `DISCORD_WEBHOOK_URL` as an environment secret in both environments.
8. Enable GitHub secret scanning and Actions. The workflows also run Gitleaks, dependency auditing,
   linting, strict typing, tests, and config validation.

### CI/CD activation order

1. Complete the Google and GitHub environment setup above before merging v2 to `main`. Keep
   `CALENDAR_SYNC_ENABLED=false` during the cutover.
2. Push v2 on a branch and open a pull request. The `CI` workflow must pass before merge.
3. Merge to `main`. CI runs again, but automatic production sync remains skipped while the enable
   variable is false.
4. Disable the PythonAnywhere scheduled task so it cannot write during or after the cutover.
5. Manually run `Calendar sync` with `dry_run=true`; review the counts in the workflow summary.
6. Run `One-time v1 migration`, enter `DELETE_FUTURE_EVENTS`, and approve the protected
   `production-migration` environment. This is the only destructive cutover step.
7. Run another manual dry run. A healthy result has zero creates, updates, and deletes, with all
   desired events reported as unchanged.
8. Set `CALENDAR_SYNC_ENABLED=true`. The workflow then runs at 03:17 and 15:17 Europe/London, and
   after every successful CI run for a push to `main`.

Both deployment workflows fail early with an explicit list of missing environment variables. The
Discord webhook is optional; omit it if failure notifications are not required.

The production workflow runs at 03:17 and 15:17 Europe/London. GitHub scheduled workflows are
best-effort, so the second run is intentional redundancy. A workflow can also be manually invoked
for one feed or in dry-run mode.

## Safe reconciliation

Each generated event is tagged with the application version, feed, and stable upstream ID. A run
loads only tagged events and computes creates, patches, deletions, and no-ops. It never touches an
unrelated or manually created event.

No deletions happen when a source request or schema validation fails. An empty desired set, too many
deletions, or an excessive deletion fraction fails the run and sends an alert. Pokémon and Valorant
run independently, so one provider outage does not prevent the other feed from syncing.

## One-time v1 cutover

1. Disable the PythonAnywhere scheduled task so there is only one writer.
2. Run the `Calendar sync` workflow manually with `dry_run` enabled and review both feeds.
3. Run `One-time v1 migration`, enter `DELETE_FUTURE_EVENTS`, and approve the
   `production-migration` environment.
4. The workflow exports future events to a private 14-day artifact, clears both dedicated
   calendars, creates tagged v2 events, and then exits.
5. Run a second dry run. Every count should be zero except `unchanged`.

To roll back, disable the production workflow, download the private backup artifact, authenticate
locally, and run:

```bash
uv run calendar-sync restore-backup \
  --backup backups/pre-v2.json \
  --confirm-restore RESTORE_EVENTS
```

Do not run restore over a populated calendar; it inserts the backed-up events and may create
duplicates. The backup can contain private calendar information and must not be committed.

## Failure guide

- **The Valorant API fails:** the maintained `vlrdevapi` client reads the public VLR match page.
- **Both providers or Pokémon fail:** that feed is left unchanged and the workflow fails.
- **Deletion safety failure:** run a dry run, verify the upstream response and filter change, then
  manually approve unsafe deletion only when the reported removals are expected.
- **Timezone disagreement:** inspect the raw source timestamp. Never add a numeric offset; correct
  the source-specific parsing contract and add a regression fixture.
- **Missed GitHub schedule:** manually dispatch the workflow. Scheduled execution is intentionally
  best-effort for this personal project.
