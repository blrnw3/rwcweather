"""DB-free day length helpers (sun centre at -0.833 deg, same convention as rwcwx.model.sun.sun_times)."""
from datetime import date, datetime, timedelta

from rwcwx.astronomy import get_all_times_rwc


def daylight_s(d: date) -> int:
    """Daylight length in seconds for a local day: sunset - sunrise as real elapsed time (DST-safe)."""
    # Naive noon like sun_times: astronomy uses time.mktime and returns naive process-local datetimes;
    # .timestamp() interprets them the same way, so the difference is true elapsed seconds in any TZ.
    t = get_all_times_rwc(datetime(d.year, d.month, d.day, 12))
    return round(t["sunset"].timestamp() - t["sunrise"].timestamp())


def daylight_change_s(d: date) -> int:
    """Change in daylight length vs the previous local day, in seconds (+ = longer)."""
    return daylight_s(d) - daylight_s(d - timedelta(days=1))
