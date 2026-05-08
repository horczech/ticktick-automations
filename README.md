# ticktick-automations

Personal TickTick automations that run on GitHub Actions.

## tag_stale

Tags TickTick tasks as `stale` when they've been untouched for >7 days and have no due date or start date attached.

### What gets tagged

A task is tagged `stale` when **all** of the following hold:

- It is not completed (`status != 1`).
- It has no `dueDate` and no `startDate`.
- It is not in a shared list or an archived list.
- Its `modifiedTime` is more than 7 days ago.
- It is not already tagged `stale`.

The tag is **sticky**: the script only ever adds it. Removing it is a manual action you take when you've triaged the task.

### Setup

1. Add two repository secrets in GitHub → Settings → Secrets and variables → Actions:
   - `TICKTICK_USERNAME`
   - `TICKTICK_PASSWORD`
2. First run as dry run: GitHub → Actions → "Tag stale TickTick tasks" → "Run workflow" → check **Dry run**. Inspect the log for surprises.
3. Second run for real (uncheck Dry run).
4. After that, the daily cron at `04:00 UTC` (~05:00–06:00 Europe/Prague) takes over.

### Local run

```bash
pip install -r requirements.txt
TICKTICK_USERNAME=you@example.com TICKTICK_PASSWORD=... DRY_RUN=true python tag_stale.py
```

### Configuration

| Env var              | Effect                                                |
| -------------------- | ----------------------------------------------------- |
| `TICKTICK_USERNAME`  | TickTick account email.                               |
| `TICKTICK_PASSWORD`  | TickTick account password (no 2FA support).           |
| `DRY_RUN`            | `true`/`1`/`yes` to print what would be tagged and exit without writes. |

### Known sharp edges

- **2FA is not supported** by `ticktick-py`'s username/password login flow. If you enable 2FA on TickTick, the script will stop working.
- **The script bypasses `client.task.update()`** and posts directly to the v2 batch endpoint that TickTick's web client uses. This was necessary because the library's `update()` method requires OAuth Bearer auth and has a `# TODO: Make tags work` flag inside it. See [CLAUDE.md](CLAUDE.md) for the full reasoning. The v2 endpoint is the same one the official web app uses, so it's likely stable, but it's an unofficial integration — TickTick could change it and break the script.
- **`ticktick-py` is pinned to v2.0.3.** Bumps require manual edit of [requirements.txt](requirements.txt) followed by re-verifying field names against the library's source if anything changes structurally.
- **GitHub Actions cron is best-effort.** "04:00 UTC" can mean anywhere from 04:00 to 05:30 UTC depending on runner load.
- **GitHub auto-disables scheduled workflows after 60 days of repo inactivity.** Push any commit at least every 60 days to keep the schedule alive.
