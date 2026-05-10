#!/usr/bin/env python3
"""Tag TickTick tasks as 'stale' when untouched for >7 days and undated."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from enum import Enum

import requests

from constants import (
    EXIT_API_ERROR,
    EXIT_MISSING_CONFIG,
    EXIT_SUCCESS,
    SKIP_TAG,
    STALE_TAG,
    STALENESS_DAYS,
    TASK_STATUS_OPEN,
)
from ticktick_client import TickTickClient


def parse_ticktick_time(raw_timestamp):
    """Parse a TickTick timestamp into an aware UTC datetime, or None."""
    if raw_timestamp is None or raw_timestamp == "":
        return None
    if isinstance(raw_timestamp, datetime):
        return raw_timestamp if raw_timestamp.tzinfo else raw_timestamp.replace(tzinfo=timezone.utc)
    iso_text = str(raw_timestamp).replace("Z", "+00:00")
    if len(iso_text) >= 5 and iso_text[-5] in "+-" and iso_text[-3] != ":":
        iso_text = iso_text[:-2] + ":" + iso_text[-2:]
    try:
        parsed = datetime.fromisoformat(iso_text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_excluded_task_list(task_list: dict) -> bool:
    """A "task list" in TickTick UI is called a "project" in the Open API."""
    if task_list.get("closed"):
        return True
    if (task_list.get("userCount") or 0) > 1:
        return True
    # Per Open API docs, `permission` is "read" | "write" | "comment". If we
    # don't have write, updating tasks in this list will 403. Skip up front.
    permission = task_list.get("permission")
    if permission is not None and permission != "write":
        return True
    kind = task_list.get("kind")
    if kind is not None and kind != "TASK":
        return True
    return False


class TaskResult(Enum):
    """Outcome of evaluating a single task in `tag_if_stale`."""
    TAGGED = "tagged"
    NO_MODIFIED_TIME = "no_modified_time"
    SKIPPED = "skipped"


def tag_if_stale(
    task: dict,
    client: TickTickClient,
    now: datetime,
    stale_cutoff: datetime,
    log_prefix: str,
    is_dry_run: bool,
) -> TaskResult:
    """Evaluate one task and tag it as stale if it qualifies."""
    # Defensive: docs say /data returns "Undone tasks", so status should
    # always be open here. Whitelist anyway in case the API ever leaks others.
    if task.get("status") != TASK_STATUS_OPEN:
        return TaskResult.SKIPPED
    # Task `kind` enum is "TEXT" | "NOTE" | "CHECKLIST". Skip note-style
    # items — they don't go stale the way actionable tasks do.
    if task.get("kind") == "NOTE":
        return TaskResult.SKIPPED
    if task.get("dueDate") or task.get("startDate"):
        return TaskResult.SKIPPED

    current_tags = task.get("tags") or []
    current_tags_lower = {(tag_name or "").lower() for tag_name in current_tags}
    if STALE_TAG in current_tags_lower:
        return TaskResult.SKIPPED
    if SKIP_TAG in current_tags_lower:
        return TaskResult.SKIPPED

    # `modifiedTime` is observed on responses but is NOT in the documented
    # Task schema (as of these docs). If it ever disappears, every task
    # will fall into this branch — caller counts these and warns at the end.
    modified_at = parse_ticktick_time(task.get("modifiedTime"))
    if modified_at is None:
        return TaskResult.NO_MODIFIED_TIME
    if modified_at > stale_cutoff:
        return TaskResult.SKIPPED

    age_days = (now - modified_at).days
    title = task.get("title") or "<untitled>"
    print(f'{log_prefix}[stale] +{age_days}d "{title}"')

    if not is_dry_run:
        task["tags"] = list(current_tags) + [STALE_TAG]
        try:
            client.post(f"/task/{task['id']}", task)
        except requests.HTTPError as error:
            print(
                f'WARN: failed to tag task {task.get("id")} '
                f'"{title}": {error}',
                file=sys.stderr,
            )
            return TaskResult.SKIPPED

    return TaskResult.TAGGED


def main() -> int:
    api_key = os.environ.get("TICKTICK_API_KEY")
    if not api_key:
        print("ERROR: TICKTICK_API_KEY must be set.", file=sys.stderr)
        return EXIT_MISSING_CONFIG

    # Tolerant of "false"/empty/missing on purpose: the GitHub Actions workflow
    # serializes its boolean input as the string "false" on unchecked manual runs,
    # and as "" on cron runs. Don't simplify to bool(os.environ.get("DRY_RUN")).
    is_dry_run = os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes")

    client = TickTickClient(api_key)

    task_lists = client.get("/project")
    if not task_lists:
        print("ERROR: /project returned no task lists — auth or account issue.", file=sys.stderr)
        return EXIT_API_ERROR

    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(days=STALENESS_DAYS)
    log_prefix = "[DRY RUN] " if is_dry_run else ""

    tagged_count = 0
    total_tasks_seen = 0
    missing_modified_count = 0
    for task_list in task_lists:
        if is_excluded_task_list(task_list):
            continue

        task_list_data = client.get(f"/project/{task_list['id']}/data")
        tasks = task_list_data.get("tasks") or []
        # /project/{id}/data already returns only undone tasks per the docs,
        # but log per-list counts in case the API ever caps the response.
        print(f'{log_prefix}[list] "{task_list.get("name")}" — {len(tasks)} task(s)')
        total_tasks_seen += len(tasks)

        for task in tasks:
            result = tag_if_stale(task, client, now, stale_cutoff, log_prefix, is_dry_run)
            if result is TaskResult.TAGGED:
                tagged_count += 1
            elif result is TaskResult.NO_MODIFIED_TIME:
                missing_modified_count += 1

    if missing_modified_count > 0:
        note_text = (
            f"NOTE: {missing_modified_count}/{total_tasks_seen} task(s) had no "
            f"parseable modifiedTime and were skipped."
        )
        print(note_text, file=sys.stderr)
        if total_tasks_seen > 0 and missing_modified_count == total_tasks_seen:
            print(
                "WARN: NO task returned a modifiedTime field. The Open API "
                "may have stopped returning it; this script depends on it.",
                file=sys.stderr,
            )

    if is_dry_run:
        print(f"[DRY RUN] Would have tagged {tagged_count} task(s) as stale.")
    else:
        print(f"Tagged {tagged_count} task(s) as stale.")
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
