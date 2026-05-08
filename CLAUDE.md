# Guidance for Claude

This repo holds personal TickTick automations that run on GitHub Actions. Each automation is a single Python script plus its own workflow file. Do not generalize early — when a second automation appears, two scripts side-by-side is fine; only extract shared code on the third.

## Locked design decisions for `tag_stale`

These were settled in a grilling session. Don't relitigate without good reason.

- **Auth: username/password only.** No OAuth credentials needed at runtime. See "ticktick-py constraints" below for why a stub OAuth object is still constructed.
- **Staleness rule:** `modifiedTime > 7 days ago` AND `dueDate is None` AND `startDate is None` AND task is in a non-shared, non-archived list. Not `createdTime` — `createdTime` is immutable and would tag long-running active work.
- **Sticky tagging.** The script only ever adds the tag, never removes it. Symmetric (add/remove) tagging was rejected because writes bump `modifiedTime`, which causes ~8-day on/off flapping.
- **`DRY_RUN` env var** for previewing without writes. No per-run cap — first run is meant to be the bulk run.
- **Tag handling: case-insensitive check-then-create.** Don't enforce color on a pre-existing `stale` tag — respect whatever the user set.
- **Notification on failure: none for now.** GitHub's default failure emails are sufficient.
- **Schedule: `0 4 * * *`** (04:00 UTC, before the user's workday in Europe/Prague).

## ticktick-py constraints (verified against v2.0.3)

The library has two real constraints that shape this script. If you change behavior, keep these in mind:

1. **`TickTickClient.__init__` requires an OAuth2 instance positionally** (`api.py:27`). It only reads `.session` and `.access_token_info` from it, so we pass `_StubOAuth` — a tiny class providing both, with a retry-equipped `requests.Session`. We never call the real OAuth2 because its constructor triggers an interactive browser flow that can't complete on a stateless runner.

2. **`client.task.update()` is unusable for our purposes.** It targets the open/v1 API which requires an OAuth Bearer token, and the implementation has a literal `# TODO: Make tags work` comment (`tasks.py:241`). We bypass it and call the v2 batch endpoint directly: `POST {BASE_URL}/batch/task` with `{"add": [], "update": [task], "delete": []}`, authenticated by the cookie set during `_login`. This is the same endpoint TickTick's own web client uses for all task mutations.

   `client.tag.create()`, `client.sync()`, and `client.task.delete()` all use v2 endpoints with cookie auth — those work fine without OAuth. Only `task.update()` is the OAuth-only outlier.

If `ticktick-py` ships a version that fixes the open API tag handling, we could revisit and use the supported `update()` path — but only if we also solve OAuth on a stateless runner (see commit history grilling-session for why we ducked that).

## Verified field names (ticktick-py v2.0.3)

From inline docstring examples in the library source:

- Task: `id`, `projectId`, `title`, `status`, `tags`, `startDate`, `dueDate`, `modifiedTime`, `createdTime`, `priority`, `items`, `etag`.
- Project: `id`, `name`, `userCount` (>1 = shared), `closed` (truthy = archived), `kind`, `groupId`, `permission`.
- Tag: `name` (lowercased on server), `label` (display case), `color`, `etag`, `parent`.

Timestamps are ISO 8601 strings like `2026-04-15T10:00:00.000+0000`. The script's `parse_ticktick_time` handles both `+0000`-style suffixes and `Z`.

## Conventions

- Python scripts live at the repo root, one file per automation: `tag_stale.py`, `next_thing.py`, etc.
- Workflows live at `.github/workflows/<script_name>.yml` and mirror the script's name.
- Pin all PyPI dependencies in `requirements.txt` to exact versions. Bump deliberately.
- Secrets are GitHub Actions secrets, never committed. Add a row to the README's "Setup" section when introducing a new secret.
