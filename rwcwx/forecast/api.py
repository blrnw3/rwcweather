"""GET /api/forecast: NWS forecast (today + tomorrow), Area Forecast Discussion highlights and active alerts for
the station, shaped by rwcwx.forecast.parse. Each part is null when NWS is unavailable (the card says so)."""
from datetime import datetime, timezone

from flask import jsonify

from rwcwx.forecast import nws, parse
from rwcwx.recap.rules import local_today


def _now() -> datetime:
    return datetime.now(timezone.utc)      # patched in tests


def build(now_utc: datetime) -> dict:
    today = local_today(now_utc)
    fc = nws.forecast()
    return dict(
        location=dict(lat=nws.LAT, lon=nws.LON,
                      url=f"https://forecast.weather.gov/MapClick.php?lat={nws.LAT}&lon={nws.LON}"),
        updated=(fc or {}).get("updateTime") or (fc or {}).get("generatedAt"),
        periods=parse.periods(fc, today),
        discussion=parse.discussion(nws.afd()),
        alerts=parse.alerts(nws.alerts()),
        today=today.isoformat(),
    )


def get_forecast():
    resp = jsonify(result=build(_now()))
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp
