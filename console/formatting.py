from datetime import datetime, timedelta, timezone

# Stored timestamps are naive UTC (datetime.utcnow().isoformat() on the API side).
# Fixed +10:00 offset matches the demo environment's local time without relying
# on browser timezone info, which Streamlit doesn't expose server-side.
LOCAL_TZ = timezone(timedelta(hours=10))


def format_local(iso_string) -> str:
    if not isinstance(iso_string, str) or not iso_string:
        return "-"
    dt_utc = datetime.fromisoformat(iso_string).replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(LOCAL_TZ).strftime("%d %b %Y, %H:%M")


def to_local_date(iso_string):
    """Local calendar date for a naive-UTC ISO timestamp (e.g. for grouping/filtering by day)."""
    dt_utc = datetime.fromisoformat(iso_string).replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(LOCAL_TZ).date()


def today_local():
    return datetime.now(timezone.utc).astimezone(LOCAL_TZ).date()
