#!/usr/bin/env python3
"""Tag TickTick tasks as 'stale' when untouched for >7 days and undated."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from requests.adapters import HTTPAdapter
from ticktick.api import TickTickClient
from urllib3.util.retry import Retry

STALE_TAG = "stale"
STALE_COLOR = "#aaaaaa"
STALENESS_DAYS = 7


class _StubOAuth:
    """Minimal stand-in for ticktick.oauth2.OAuth2.

    The TickTickClient constructor requires an OAuth2 instance, but only reads
    `.session` and `.access_token_info` from it. The v2 batch endpoints we use
    authenticate via the cookie set during username/password login, so the
    Bearer token is never actually needed. Subclassing OAuth2 would trigger its
    interactive browser flow on construction, which doesn't work on a stateless
    GitHub Actions runner.
    """

    def __init__(self):
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=(405, 500, 502, 504),
            allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE"]),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session = requests.Session()
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.access_token_info = None


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


def is_excluded_project(project) -> bool:
    if project.get("closed"):
        return True
    if (project.get("userCount") or 0) > 1:
        return True
    return False


def update_task_v2(client: TickTickClient, task: dict) -> None:
    """Update a task via the v2 batch endpoint (cookie auth, supports tags)."""
    url = client.BASE_URL + "batch/task"
    payload = {"add": [], "update": [task], "delete": []}
    response = client.http_post(
        url, json=payload, cookies=client.cookies, headers=client.HEADERS
    )
    errors = response.get("id2error") if isinstance(response, dict) else None
    if errors:
        raise RuntimeError(f"TickTick rejected update for task {task.get('id')}: {errors}")


def main() -> int:
    username = os.environ.get("TICKTICK_USERNAME")
    password = os.environ.get("TICKTICK_PASSWORD")
    if not username or not password:
        print("ERROR: TICKTICK_USERNAME and TICKTICK_PASSWORD must be set.", file=sys.stderr)
        return 2

    dry_run = os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes")

    client = TickTickClient(username, password, _StubOAuth())

    tasks = client.state.get("tasks") or []
    if not tasks:
        print("ERROR: no tasks returned — auth likely failed silently.", file=sys.stderr)
        return 3

    existing_tag_names = {(t.get("name") or "").lower() for t in (client.state.get("tags") or [])}
    if STALE_TAG not in existing_tag_names and not dry_run:
        client.tag.create(STALE_TAG, color=STALE_COLOR)

    skip_project_ids = {
        p.get("id")
        for p in (client.state.get("projects") or [])
        if is_excluded_project(p)
    }

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=STALENESS_DAYS)
    prefix = "[DRY RUN] " if dry_run else ""

    tagged = 0
    for task in tasks:
        if task.get("status") == 1:
            continue
        if task.get("projectId") in skip_project_ids:
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
            update_task_v2(client, task)

        tagged += 1

    if dry_run:
        print(f"[DRY RUN] Would have tagged {tagged} task(s) as stale.")
    else:
        print(f"Tagged {tagged} task(s) as stale.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
