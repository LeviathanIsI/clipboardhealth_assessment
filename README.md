# Bellhaven CRM Sync

Reconciles the Bellhaven Senior Living website against the CRM sandbox and
proposes fixes for human review. Nothing is ever written to the CRM without an
explicit approval in the review app.

## Layout

| Path | Role |
|---|---|
| `pipeline/scrape.py` | Crawls the paginated `/communities` directory **and** scans the homepage for directory-absent links; parses every detail page. Fails loudly on zero parses; warns when the location count moves >20% vs the previous snapshot. |
| `pipeline/normalize.py` | Shared address/name/person/phone normalization keys used by both sides of the comparison. |
| `pipeline/match.py` | Matching + classification; emits proposals. Pure — no network, no hardcoded records. |
| `pipeline/executor.py` | The **only** module that writes to the CRM. Runs a proposal's ops in order, resolves `{new_id}` captures, appends `[sync-bot YYYY-MM-DD]` notes. |
| `pipeline/api_client.py` | Thin CRM client: exhaustive pagination for reads; write helpers used only by the executor. |
| `pipeline/config.py` | Env/.env-driven configuration (API base, site base, token, data dir). |
| `store.py` | SQLite layer (`data/sync.db`, git-ignored): proposals, decisions, run history, idempotency. |
| `run_pipeline.py` | Scheduler entry: scrape + match + store proposals. Never writes to the CRM. |
| `app.py` | Flask review UI: tier-grouped proposal cards with before→after diffs, human-readable evidence facts (raw JSON behind a toggle), color-coded badges with a collapsible legend, approve/reject per proposal, bulk-approve HIGH, run summary. |
| `schedule/` | Daily-run artifacts: `crontab.txt` (local cron) and `daily-sync.yml` (GitHub Actions). See Scheduling below. |
| `recon/` | Phase-1 reconnaissance: raw API pulls, scraped-site snapshots (`html/`), parsed locations, and `findings.md` — the data-quality analysis the pipeline's generic rules were sanity-checked against. |

## Setup & running

```bash
pip install -r requirements.txt
cp .env.example .env     # then paste your CRM token into .env — that's it
python run_pipeline.py   # generate/refresh proposals (read-only vs CRM)
python app.py            # review UI at http://127.0.0.1:5000
```

The CRM token is **not** stored in code. Resolution order: a real
`CRM_API_TOKEN` environment variable (shell export or the Actions secret)
wins first, then the git-ignored `.env` at the repo root; if neither is set,
startup fails with instructions. `.env.example` is the committed template.

> **Note for reviewers:** the sandbox token appeared in tracked files in
> earlier commits, so it exists in this repo's git history. It was removed
> from the working tree in the secrets-cleanup commit; history was
> deliberately left unrewritten. In a real project the exposed token would
> be rotated and history scrubbed (e.g. `git filter-repo`).

Other env-overridable config: `BELLHAVEN_API_BASE`, `BELLHAVEN_SITE_BASE`,
`BELLHAVEN_DATA_DIR`.

## Scheduling

Both schedule files are **artifacts** — checked in to show the production
configuration, not live in this repo. The intent for both is a daily run at
8:00am EST.

- `schedule/daily-sync.yml` — GitHub Actions workflow. GitHub cron runs in
  UTC, so it fires at `0 13 * * *` (13:00 UTC = 8am EST; during EDT this
  drifts to 9am local). It passes the CRM token as `CRM_API_TOKEN` from
  `secrets.CRM_API_TOKEN`. To go live it needs: the secret registered, the
  file moved to `.github/workflows/`, and `data/sync.db` persisted between
  runs (actions/cache or committing the db) — the runner filesystem is
  ephemeral and idempotency depends on the decision store.
- `schedule/crontab.txt` — the same intent for a local machine. Local cron
  uses the system timezone, so it is simply `0 8 * * *` on an EST host.

Either way the scheduled entry is `run_pipeline.py`, which is read-only
against the CRM — approvals only ever happen by hand in the review app.

## Classification rules (all generic, computed at runtime)

- The Bellhaven parent account is discovered by name pattern
  (`(Parent Account)` + brand token), never by id.
- **Match signals**: address-key equality (street+city+state) is strong; exact
  name-key equality counts only within the same city/state (PO-Box/blank CRM
  streets fall back to name+city+state); website administrator ↔ CRM contact
  and phone equality corroborate. Name similarity across different cities is
  never a match (operators reuse facility names).
- **CONFIRMED** / **NEEDS_FIX** (name drift and/or wrong-or-missing parent) /
  **MISSING** (create under the Bellhaven parent; same-city name-only overlaps
  are recorded as near-misses, not matches) / **ORPHANED** (Active Bellhaven
  child with no website presence → `Needs Review`, never auto-Inactive).
- **Cosmetic renames**: a CONFIRMED match whose *raw* name (entity-decoded,
  trimmed) still differs from the website spelling gets a HIGH-tier `RENAME`
  proposal. Only CONFIRMED winners emit these, so accounts handled by
  re-parent/CHOW/duplicate proposals (which already apply the website
  spelling) never receive a second rename.
- **Duplicates**: ≥2 accounts sharing a website location's address key. The
  survivor is the website-corroborated account (name/contact), then
  Bellhaven-parent, then revenue history. Losers get `duplicate_of_account` +
  Inactive; their contacts are re-pointed to the survivor. Same-address pairs
  *not* anchored by a website location are left to the divestiture rule —
  otherwise it would fight the CHOW logic.
- **CHOW rule**: any proposed re-parent of an account with
  `lifetime_revenue > 0` **and** `outstanding_ar > 0` becomes a
  create-successor-then-link sequence (`chow_current_account` on the old
  account; old account otherwise untouched). Divestitures (Bellhaven child off
  the website whose address hosts another operator's account) with the same
  billing constraint get only `chow_current_account` + note; without the
  constraint they go to `Needs Review` for a human.
- Accounts that already have `chow_current_account` or `duplicate_of_account`
  set are treated as superseded and excluded from matching, duplicate
  detection, and orphan checks — this is what makes re-runs converge after
  approvals are applied.

## Idempotency

`proposal_id = SHA256(type + target + ordered ops)`. Decided/applied proposals
are never re-opened; pending ones are refreshed in place; pending proposals
whose condition disappeared are marked stale and hidden. Note text never embeds
dates at proposal time (the executor stamps the date at apply time), so hashes
are stable across days.

## Proposal types

`RENAME` (cosmetic spelling fix on a confirmed match) · `UPDATE_ACCOUNT`
(name and/or parent fix, single PATCH) · `CREATE_ACCOUNT` (new account under
the Bellhaven parent from website details) · `CHOW_REPARENT` (create
successor, then link `chow_current_account`) · `CHOW_DIVESTITURE`
(`chow_current_account` link only, everything else untouched) ·
`MARK_DUPLICATE` (deactivate + `duplicate_of_account` + re-point contacts) ·
`NEEDS_REVIEW` (status flag for a human decision). The review UI's badge
legend describes each in place.

## Confidence tiers

HIGH (cosmetic renames of confirmed matches; single-field fixes with
address + name/contact corroboration; website-corroborated duplicates),
MEDIUM (creates, CHOW sequences, multi-field fixes, uncorroborated
duplicates), LOW (orphans, divestitures, near-miss creates). Tiers only
affect grouping and the bulk button — **every** write requires an explicit
human approval.
