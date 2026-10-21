"""DB-free day length and twilight helpers (sunrise/sunset: sun centre at -0.833 deg; civil twilight -6 deg;
astronomical twilight -18 deg). rwcwx.model.sun re-exports sun_times."""
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


def sun_times(d: date) -> dict:
    """Sunrise/sunset as epoch ms, same convention as the classifier (sun centre at -0.833 deg)."""
    # Naive noon, like get_all_times_rwc's own default: astronomy uses time.mktime, and an aware
    # datetime carries tm_isdst=1 in summer, which glibc rejects when the process zone is UTC (prod).
    times = get_all_times_rwc(datetime(d.year, d.month, d.day, 12))
    sr, ss = times["sunrise"], times["sunset"]
    dawn, dusk = times.get("dawn", sr), times.get("dusk", ss)
    # Astronomical twilight (sun 18 deg below the horizon): "nightEnd" / "night" in suncalc's names. None when
    # the sun never gets that low (doesn't happen at 37.5 N, but the API must not fail if it does).
    astro_dawn, astro_dusk = times.get("nightEnd"), times.get("night")

    def ms(dt):
        # astronomy returns naive datetimes in the process's local zone; .timestamp() interprets them the same way
        return int(dt.timestamp() * 1000) if dt is not None else None

    return dict(sunrise=ms(sr), sunset=ms(ss), dawn=ms(dawn), dusk=ms(dusk),
                astro_dawn=ms(astro_dawn), astro_dusk=ms(astro_dusk),
                daylight_h=round(times["daylight_secs"] / 3600, 2))
