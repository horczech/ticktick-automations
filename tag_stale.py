#!/usr/bin/env python3
"""Tag TickTick tasks as 'stale' when untouched for >7 days and undated."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import requests

BASE_URL = "https://api.ticktick.com/open/v1"
STALE_TAG = "stale"
SKIP_TAG = "someday"
STALENESS_DAYS = 7
HTTP_TIMEOUT = 30


def parse_ticktick_time(value):
    """Parse a TickTick timestamp into an aware UTC datetime, or None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).replace("Z", "+00:00")
    if len(s) >= 5 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_excluded_project(project: dict) -> bool:
    if project.get("closed"):
        return True
    if (project.get("userCount") or 0) > 1:
        return True
    # Per Open API docs, `permission` is "read" | "write" | "comment". If we
    # don't have write, updating tasks in this project will 403. Skip up front.
    permission = project.get("permission")
    if permission is not None and permission != "write":
        return True
    kind = project.get("kind")
    if kind is not None and kind != "TASK":
        return True
    return False


def main() -> int:
    api_key = os.environ.get("TICKTICK_API_KEY")
    if not api_key:
        print("ERROR: TICKTICK_API_KEY must be set.", file=sys.stderr)
        return 2

    # Tolerant of "false"/empty/missing on purpose: the GitHub Actions workflow
    # serializes its boolean input as the string "false" on unchecked manual runs,
    # and as "" on cron runs. Don't simplify to bool(os.environ.get("DRY_RUN")).
    dry_run = os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes")

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })

    def get(path: str):
        r = session.get(f"{BASE_URL}{path}", timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()

    def post(path: str, payload):
        r = session.post(f"{BASE_URL}{path}", json=payload, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json() if r.text else None

    projects = get("/project")
    if not projects:
        print("ERROR: /project returned no projects — auth or account issue.", file=sys.stderr)
        return 3

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=STALENESS_DAYS)
    prefix = "[DRY RUN] " if dry_run else ""

    tagged = 0
    seen_tasks = 0
    missing_modified = 0
    for project in projects:
        if is_excluded_project(project):
            continue

        data = get(f"/project/{project['id']}/data")
        tasks = data.get("tasks") or []
        # /project/{id}/data already returns only undone tasks per the docs,
        # but log per-project counts in case the API ever caps the response.
        print(f'{prefix}[project] "{project.get("name")}" — {len(tasks)} task(s)')
        seen_tasks += len(tasks)

        for task in tasks:
            # Defensive: docs say /data returns "Undone tasks", so status should
            # always be 0 here. Whitelist anyway. (Task status enum: 0=Open, 2=Completed.)
            if task.get("status") != 0:
                continue
            # Task `kind` enum is "TEXT" | "NOTE" | "CHECKLIST". Skip note-style
            # items — they don't go stale the way actionable tasks do.
            if task.get("kind") == "NOTE":
                continue
            if task.get("dueDate") or task.get("startDate"):
                continue

            current_tags = task.get("tags") or []
            tag_set = {(t or "").lower() for t in current_tags}
            if STALE_TAG in tag_set:
                continue
            if SKIP_TAG in tag_set:
                continue

            # `modifiedTime` is observed on responses but is NOT in the documented
            # Task schema (as of these docs). If it ever disappears, every task
            # will fall into this branch — we count it and warn at the end.
            modified = parse_ticktick_time(task.get("modifiedTime"))
            if modified is None:
                missing_modified += 1
                continue
            if modified > threshold:
                continue

            age_days = (now - modified).days
            title = task.get("title") or "<untitled>"
            print(f'{prefix}[stale] +{age_days}d "{title}"')

            if not dry_run:
                task["tags"] = list(current_tags) + [STALE_TAG]
                try:
                    post(f"/task/{task['id']}", task)
                except requests.HTTPError as e:
                    print(
                        f'WARN: failed to tag task {task.get("id")} '
                        f'"{title}": {e}',
                        file=sys.stderr,
                    )
                    continue

            tagged += 1

    if missing_modified > 0:
        msg = (
            f"NOTE: {missing_modified}/{seen_tasks} task(s) had no parseable "
            f"modifiedTime and were skipped."
        )
        print(msg, file=sys.stderr)
        if seen_tasks > 0 and missing_modified == seen_tasks:
            print(
                "WARN: NO task returned a modifiedTime field. The Open API "
                "may have stopped returning it; this script depends on it.",
                file=sys.stderr,
            )

    if dry_run:
        print(f"[DRY RUN] Would have tagged {tagged} task(s) as stale.")
    else:
        print(f"Tagged {tagged} task(s) as stale.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
