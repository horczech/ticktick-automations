# Guidance for Claude

This repo holds personal TickTick automations that run on GitHub Actions. Each automation is a single Python script plus its own workflow file. Do not generalize early — when a second automation appears, two scripts side-by-side is fine; only extract shared code on the third.

## Locked design decisions for `tag_stale`

These were settled in a grilling session. Don't relitigate without good reason.

- **Auth: TickTick personal API key** (the `tp_…` style key from Settings → Account → API Keys), used as `Authorization: Bearer tp_…` against the Open API. Probed: works against `/open/v1/*`. Does **not** work against the v2 API at `/api/v2/*` (returns 500). Earlier attempts at username/password auth via `ticktick-py` were abandoned because the user is logged into TickTick via Google OAuth and has no native password.
- **Staleness rule:** `modifiedTime > 7 days ago` AND `dueDate is None` AND `startDate is None` AND task is in a non-shared, non-archived list. Not `createdTime` — `createdTime` is immutable and would tag long-running active work.
- **Sticky tagging.** The script only ever adds the tag, never removes it. Symmetric (add/remove) tagging was rejected because writes bump `modifiedTime`, causing ~8-day on/off flapping.
- **`DRY_RUN` env var** for previewing without writes. No per-run cap.
- **Notification on failure: none for now.** GitHub's default failure emails are sufficient.
- **Schedule: `0 4 * * *`** (04:00 UTC, before the user's workday in Europe/Prague).

## TickTick Open API constraints

What the Open API exposes (and what it doesn't) shapes how this script is built. If you change behavior, keep these in mind:

- **No `/tag` endpoints.** The user must pre-create the `stale` tag manually in the TickTick UI. The script doesn't try to create it.
- **No "list all tasks" endpoint.** To enumerate tasks you must list projects (`GET /open/v1/project`) and then fetch each project's tasks (`GET /open/v1/project/{projectId}/data`). One round-trip per project.
- **The Inbox is not in `/project`.** It's a pseudo-project with id `inbox{userId}` (the user id is exposed via `/open/v1/user/profile`). The script currently does not touch inbox tasks. If the user accumulates stale tasks in the inbox and complains, extend `main()` to also fetch `/project/inbox{user_id}/data` after computing the user id from `/user/profile`.
- **Task updates use the same dict shape as the v2 task object** (confirmed via the Open API responses): `id`, `projectId`, `title`, `tags`, `status`, `startDate`, `dueDate`, `modifiedTime`, etc. Posting the full task dict to `POST /open/v1/task/{taskId}` works. Tag updates do go through (the unofficial `ticktick-py` library had a stale `# TODO: Make tags work` comment about its own buggy serialization, not about an API limitation).

## Verified field names

From task JSON responses on the Open API:

- Task: `id`, `projectId`, `title`, `status`, `tags`, `startDate`, `dueDate`, `modifiedTime`, `createdTime`, `priority`, `items`, `etag`.
- Project: `id`, `name`, `userCount` (>1 = shared), `closed` (truthy = archived), `kind`, `groupId`, `permission`.

Timestamps are ISO 8601 strings like `2026-04-15T10:00:00.000+0000`. The script's `parse_ticktick_time` handles both `+0000`-style suffixes and `Z`.

## Conventions

- Python scripts live at the repo root, one file per automation: `tag_stale.py`, `next_thing.py`, etc.
- Workflows live at `.github/workflows/<script_name>.yml` and mirror the script's name.
- Pin all PyPI dependencies in `requirements.txt` to exact versions. Bump deliberately.
- Secrets are GitHub Actions secrets, never committed. Add a row to the README's "Setup" section when introducing a new secret.
