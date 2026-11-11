from datetime import UTC, datetime


def format_utc(moment: datetime) -> str:
    """Render the TEXT timestamp format the schema checks: ``YYYY-MM-DDTHH:MM:SSZ`` in UTC."""
    if moment.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now() -> str:
    return format_utc(datetime.now(UTC))
