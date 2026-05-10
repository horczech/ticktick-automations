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
- It is not tagged `someday`.

The tag is **sticky**: the script only ever adds it. Removing it is a manual action you take when you've triaged the task.

### Tags the script reads

| Tag | Set by | Effect |
| --- | --- | --- |
| `stale` | The script | Marks a task as untouched for >7 days. The script will not re-tag a task that already has it. |
| `someday` | You, manually in TickTick | Opt-out. Any task tagged `someday` is permanently skipped by the staleness check, even if it would otherwise qualify. Use this for tasks you're intentionally letting sit (long-term ideas, reference items, things you'll get to eventually). Remove the tag to bring the task back under the script's purview. |

### Setup

1. **In TickTick (one-time, manual):**
   - **Generate an API key.** Settings → Account → API Keys → Add New Key. Copy the full key (starts with `tp_`). The TickTick Open API has no `/tag` endpoints, so the script can't auto-create the tag.
   - **Manually create a tag named `stale`.** Right-click in the sidebar → Add Tag → name `stale`, color `#aaaaaa` (or whatever you prefer).
   - **Optional: create a tag named `someday`** (any color) for the opt-out workflow described in *Tags the script reads* above. You only need this if you plan to use the opt-out — TickTick will let you create it on first use.

2. **In GitHub:**
   - Push this repo to GitHub if you haven't yet.
   - Add one repository secret: Settings → Secrets and variables → Actions → New repository secret:
     - `TICKTICK_API_KEY` = the `tp_…` key from step 1.

3. **First run as a dry run:** GitHub → Actions → "Tag stale TickTick tasks" → "Run workflow" → check **Dry run**. Inspect the log for surprises.

4. **Second run for real** (uncheck Dry run).

5. After that, the daily cron at `04:00 UTC` (~05:00–06:00 Europe/Prague) takes over.

### Local run

```bash
pip install -r requirements.txt
TICKTICK_API_KEY=tp_... DRY_RUN=true python3 tag_stale.py
```

### Configuration

| Env var             | Effect                                                |
| ------------------- | ----------------------------------------------------- |
| `TICKTICK_API_KEY`  | Personal API key from TickTick → Settings → Account → API Keys. |
| `DRY_RUN`           | `true`/`1`/`yes` to print what would be tagged and exit without writes. |

### Known sharp edges

- **Inbox tasks are not iterated.** The Open API's `/project` listing does not include the special "Inbox" pseudo-project, so untouched inbox tasks aren't visible to the script. If your inbox accumulates stale tasks, you'll need to either move them to a real list or extend the script (see [CLAUDE.md](CLAUDE.md) for notes on how).
- **`stale` tag must exist beforehand.** The Open API exposes no tag CRUD endpoints. If the tag doesn't exist when the script applies it, TickTick may reject the update silently or create a phantom tag with default color.
- **No "list all tasks" endpoint.** The script makes one HTTP call per project to fetch tasks. If you have many projects, the script's runtime grows linearly. For ~20 projects this is still a few seconds — fine.
- **GitHub Actions cron is best-effort.** "04:00 UTC" can mean anywhere from 04:00 to 05:30 UTC depending on runner load.
- **GitHub auto-disables scheduled workflows after 60 days of repo inactivity.** Push any commit at least every 60 days to keep the schedule alive.
