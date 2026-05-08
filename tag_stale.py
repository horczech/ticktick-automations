#!/usr/bin/env python3
"""Tag TickTick tasks as 'stale' when untouched for >7 days and undated."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import requests

BASE_URL = "https://api.ticktick.com/open/v1"
STALE_TAG = "stale"
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
    return False


def main() -> int:
    api_key = os.environ.get("TICKTICK_API_KEY")
    if not api_key:
        print("ERROR: TICKTICK_API_KEY must be set.", file=sys.stderr)
        return 2

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
    for project in projects:
        if is_excluded_project(project):
            continue

        data = get(f"/project/{project['id']}/data")
        tasks = data.get("tasks") or []

        for task in tasks:
            if task.get("status") == 1:
                continue
            if task.get("dueDate") or task.get("startDate"):
                continue

            current_tags = task.get("tags") or []
            if any((t or "").lower() == STALE_TAG for t in current_tags):
                continue

            modified = parse_ticktick_time(task.get("modifiedTime"))
            if modified is None or modified > threshold:
                continue

            age_days = (now - modified).days
            title = task.get("title") or "<untitled>"
            print(f'{prefix}[stale] +{age_days}d "{title}"')

            if not dry_run:
                task["tags"] = list(current_tags) + [STALE_TAG]
                post(f"/task/{task['id']}", task)

            tagged += 1

    if dry_run:
        print(f"[DRY RUN] Would have tagged {tagged} task(s) as stale.")
    else:
        print(f"Tagged {tagged} task(s) as stale.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
