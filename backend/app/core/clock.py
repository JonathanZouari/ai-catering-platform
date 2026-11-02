"""Business time: dates are decided in Israel time, whatever the server's timezone."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

BUSINESS_TZ = ZoneInfo("Asia/Jerusalem")


def today() -> date:
    return datetime.now(BUSINESS_TZ).date()
