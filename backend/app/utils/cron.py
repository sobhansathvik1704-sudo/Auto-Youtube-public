from datetime import datetime

from croniter import croniter


def validate_cron_expression(cron_expression: str) -> bool:
    """Return True if the cron expression is syntactically valid."""
    return croniter.is_valid(cron_expression)


def calculate_next_run(cron_expression: str, timezone_str: str = "UTC") -> datetime:
    """Calculate the next run datetime (UTC) for a given cron expression and timezone."""
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone_str)
    now = datetime.now(tz)
    cron = croniter(cron_expression, now)
    next_run = cron.get_next(datetime)
    # Attach the local timezone so astimezone works correctly
    if next_run.tzinfo is None:
        next_run = next_run.replace(tzinfo=tz)
    return next_run.astimezone(ZoneInfo("UTC"))


def cron_interval_seconds(cron_expression: str) -> float:
    """Return the average interval in seconds between two consecutive runs."""
    from datetime import timezone

    now = datetime.now(timezone.utc)
    cron = croniter(cron_expression, now)
    first = cron.get_next(float)
    second = cron.get_next(float)
    return second - first
