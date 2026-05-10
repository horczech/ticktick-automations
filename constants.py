"""Constants shared across the automations in this repo."""

# Tag names. TickTick stores tag names lowercased on the server.
STALE_TAG = "stale"
SKIP_TAG = "someday"

# Staleness threshold (days). A task is considered stale when its
# `modifiedTime` is older than this.
STALENESS_DAYS = 7

# TickTick Open API base URL. All endpoint paths are appended to this.
TICKTICK_API_BASE_URL = "https://api.ticktick.com/open/v1"

# HTTP request timeout (seconds) for TickTick API calls.
HTTP_TIMEOUT = 30

# TickTick task `status` enum values (per Open API docs).
TASK_STATUS_OPEN = 0
TASK_STATUS_COMPLETED = 2

# Process exit codes. 0 = success; non-zero = failure (any value).
# Specific values are diagnostic only — GitHub Actions only branches on zero/non-zero.
EXIT_SUCCESS = 0
EXIT_MISSING_CONFIG = 2
EXIT_API_ERROR = 3
