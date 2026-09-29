# Automation and operations guide

This guide explains how GitHub Actions tests, deploys, schedules and protects Calendar Sync.

## Workflow overview

| Workflow | File | Trigger | Purpose |
| --- | --- | --- | --- |
| CI | `.github/workflows/ci.yml` | Pull requests and pushes to `main` | Security, formatting, linting, typing, tests, config validation and dependency audit |
| Calendar sync | `.github/workflows/sync.yml` | Manual, twice daily, and successful push CI on `main` | Reconcile one or both feeds with Google Calendar |
| One-time v1 migration | `.github/workflows/migrate.yml` | Manual only | Back up, clear and rebuild future v1 calendar events |
| Dependabot | `.github/dependabot.yml` | Weekly | Propose Python and GitHub Actions dependency updates |

Both calendar workflows share the `production-calendar-sync` concurrency group. Runs do not cancel
one another, so a migration and normal sync cannot write concurrently.

## CI workflow

CI checks out complete Git history and runs:

1. Gitleaks secret scanning;
2. locked development dependency installation;
3. Ruff formatting check;
4. Ruff linting;
5. strict mypy type checking;
6. pytest with coverage output;
7. configuration validation;
8. `pip-audit` dependency vulnerability scanning.

CI requires no calendar credentials. A pull request should not be merged until this workflow passes.

## Production sync workflow

Automatic production runs occur at 03:17 and 15:17 Europe/London and after successful CI for a
push to `main`. These automatic paths run only when the repository variable below is exactly:

```text
CALENDAR_SYNC_ENABLED=true
```

Manual runs remain available while the flag is false, which allows safe setup and dry runs.

### Manual inputs

- `feed`: `all`, `pokemon_go`, or `valorant`.
- `dry_run`: calculate and report changes without writing. Defaults to `true`.
- `allow_unsafe_deletes`: bypass configured deletion thresholds. Defaults to `false`.
- `no_deletes`: apply creates and updates while preserving every existing event. The summary reports
  preserved stale events as `deletions_skipped`. Defaults to `false`.

`allow_unsafe_deletes` and `no_deletes` are mutually exclusive. Use `no_deletes` when a provider
returns a known partial schedule and you still need to apply safe creates or updates.

The workflow writes the final JSON output into the GitHub Actions job summary.

## Required GitHub configuration

Create these repository variables under **Settings → Secrets and variables → Actions → Variables**:

| Variable | Value |
| --- | --- |
| `CALENDAR_SYNC_ENABLED` | `false` during setup; `true` after migration and verification |
| `GCP_PROJECT_ID` | Google Cloud project ID |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Full `projects/NUMBER/locations/global/workloadIdentityPools/POOL/providers/PROVIDER` name |
| `GCP_SERVICE_ACCOUNT` | Service-account email shared with both calendars |
| `POKEMON_GO_CALENDAR_ID` | Pokémon destination calendar ID |
| `VALORANT_CALENDAR_ID` | VALORANT destination calendar ID |

Create two GitHub environments:

- `production`: no required reviewer, so schedules can run unattended;
- `production-migration`: a required reviewer for the destructive cutover.

`DISCORD_WEBHOOK_URL` is optional. If used, store it as an environment secret in both environments,
not as a repository variable.

## Google Workload Identity Federation

GitHub Actions does not need a permanent service-account JSON key. GitHub issues an OIDC identity
token for a workflow run; Google validates the repository and branch claims, then issues temporary
credentials that impersonate the calendar service account.

The workflow already grants `contents: read` and `id-token: write`, checks out the repository before
authentication, and passes the provider and service-account values to
`google-github-actions/auth`.

### One-time Google Cloud setup

Open Google Cloud Shell and set:

```bash
PROJECT_ID="your-project-id"
SERVICE_ACCOUNT_EMAIL="your-service-account@your-project-id.iam.gserviceaccount.com"
REPOSITORY="arekbauer/Event-Management-Automation"
POOL_ID="github-actions"
PROVIDER_ID="calendar-sync"

gcloud config set project "$PROJECT_ID"
```

Enable the APIs and obtain the numeric project number:

```bash
gcloud services enable \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  calendar-json.googleapis.com \
  --project="$PROJECT_ID"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" \
  --format='value(projectNumber)')"
```

Create the pool and provider:

```bash
gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --display-name="Calendar Sync GitHub provider" \
  --issuer-uri="https://token.actions.githubusercontent.com/" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository_owner=='arekbauer' && assertion.repository=='${REPOSITORY}' && assertion.ref=='refs/heads/main'"
```

Allow only this repository identity to impersonate the service account:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  "$SERVICE_ACCOUNT_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPOSITORY}"
```

Get the provider value for `GCP_WORKLOAD_IDENTITY_PROVIDER`:

```bash
gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --format="value(name)"
```

The output must contain the numeric project number and the `/providers/...` suffix. IAM changes can
take several minutes to propagate.

### Calendar permissions

In Google Calendar, share each destination calendar with `GCP_SERVICE_ACCOUNT` and grant **Make
changes to events**. Google Cloud IAM alone does not grant access to a user's calendar.

## Routine change and deployment process

1. Create a branch from current `main`.
2. Change configuration or code and add a regression test.
3. Run the local checks from `docs/CONFIGURATION.md`.
4. Run a local or manual GitHub dry sync and review the proposed changes.
5. Push the branch and open a pull request.
6. Wait for CI to pass and review dependency/security findings.
7. Merge to `main`.
8. Successful main-branch CI triggers production sync when `CALENDAR_SYNC_ENABLED=true`.
9. Inspect the production workflow summary.

To stop all automatic writes without changing code, set `CALENDAR_SYNC_ENABLED=false`. Manual dry
runs still work.

## First deployment and v1 migration

1. Configure Google WIF, repository variables and GitHub environments.
2. Keep `CALENDAR_SYNC_ENABLED=false`.
3. Merge v2 into `main` and confirm CI passes.
4. Disable the PythonAnywhere scheduled task so only one system can write.
5. Manually run **Calendar sync** with `feed=all`, `dry_run=true` and
   `allow_unsafe_deletes=false`.
6. Manually run **One-time v1 migration**, enter `DELETE_FUTURE_EVENTS`, and approve the
   `production-migration` environment.
7. Download the private `pre-v2-calendar-backup` artifact. It is retained for 14 days.
8. Run another dry sync. A clean result has zero creates, updates and deletes; desired events are
   unchanged.
9. Set `CALENDAR_SYNC_ENABLED=true`.

The migration affects future events in the two dedicated calendars. It validates both sources and
refuses an empty desired feed before it deletes anything.

## Troubleshooting

- **The sync job is skipped:** check `CALENDAR_SYNC_ENABLED`; automatic runs require `true`.
- **The manual workflow is missing:** workflow dispatch is available only after the workflow exists
  on the default branch.
- **Google authentication reports an invalid target:** the provider variable must be the full
  provider name using the project number, not project ID or pool-only name.
- **Service-account token permission is denied:** check the `roles/iam.workloadIdentityUser` binding,
  mapped `attribute.repository`, exact repository spelling, and allow time for propagation.
- **Calendar returns not found or forbidden:** verify the calendar ID and share that calendar with
  the service-account email using event-edit permission.
- **A source fails:** its calendar remains unchanged and the run fails. VALORANT attempts VLRdevAPI
  after a primary-provider failure.
- **Deletion safety blocks a run:** use a dry run to verify the provider and filters. Override the
  guard only when every proposed deletion is expected.
- **A schedule is delayed:** GitHub schedules are best-effort. Dispatch a manual run if necessary;
  the second daily schedule provides redundancy.
- **Timezone output is wrong:** inspect the raw timestamp and add a regression test. Never replace
  the IANA timezone with a hard-coded numeric offset.
