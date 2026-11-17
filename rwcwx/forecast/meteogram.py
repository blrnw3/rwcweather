"""Shape an Open-Meteo forecast payload into the 10-day meteogram series (no I/O)."""
from datetime import datetime
from typing import List, Optional, Tuple

from rwcwx.config import TZ, TZ_NAME

# WMO weather interpretation codes (Open-Meteo).
WMO = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Heavy showers",
    85: "Light snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail",
}


def parse_local(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt


def ms(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    return int(dt.timestamp() * 1000)


def weather_desc(code) -> Optional[str]:
    if code is None:
        return None
    try:
        return WMO.get(int(code), "Code " + str(int(code)))
    except (TypeError, ValueError):
        return None


def _pairs(times: List[str], values: Optional[list]) -> List[list]:
    out = []
    if not values:
        return out
    for t, v in zip(times, values):
        dt = parse_local(t)
        if dt is None or v is None:
            continue
        out.append([ms(dt), v])
    return out


def daily_rows(data: dict) -> List[dict]:
    daily = data.get("daily") or {}
    times = daily.get("time") or []
    out = []
    for i, day in enumerate(times):
        start = parse_local(day + "T00:00") if isinstance(day, str) and "T" not in day else parse_local(day)
        if start is None:
            continue
        code = (daily.get("weather_code") or [None] * (i + 1))[i]
        def col(name):
            vals = daily.get(name) or []
            return vals[i] if i < len(vals) else None
        out.append(dict(
            date=start.date().isoformat(),
            start=ms(start),
            label=start.strftime("%a ") + str(start.day) + start.strftime(" %b"),
            tmax=col("temperature_2m_max"),
            tmin=col("temperature_2m_min"),
            precip=col("precipitation_sum"),
            pop=col("precipitation_probability_max"),
            wind_max=col("wind_speed_10m_max"),
            gust_max=col("wind_gusts_10m_max"),
            weather_code=code,
            weather=weather_desc(code),
        ))
    return out


def series(data: Optional[dict]) -> Optional[dict]:
    """Chart-ready series. Temperatures °C, rain mm, wind mph, pressure mb (hPa)."""
    if not data or not isinstance(data.get("hourly"), dict):
        return None
    hourly = data["hourly"]
    times = hourly.get("time") or []
    if not times:
        return None
    return dict(
        source="open-meteo",
        model=data.get("model") or "gfs_seamless",
        timezone=data.get("timezone") or TZ_NAME,
        elevation=data.get("elevation"),
        units=dict(temp="°C", precip="mm", wind="mph", pop="%", cloud="%", pressure="mb"),
        temp=_pairs(times, hourly.get("temperature_2m")),
        dew=_pairs(times, hourly.get("dew_point_2m")),
        precip=_pairs(times, hourly.get("precipitation")),
        pop=_pairs(times, hourly.get("precipitation_probability")),
        cloud=_pairs(times, hourly.get("cloud_cover")),
        wind=_pairs(times, hourly.get("wind_speed_10m")),
        gust=_pairs(times, hourly.get("wind_gusts_10m")),
        pressure=_pairs(times, hourly.get("surface_pressure")),
        weather=[
            dict(t=ms(parse_local(t)), code=c, desc=weather_desc(c))
            for t, c in zip(times, hourly.get("weather_code") or [])
            if parse_local(t) is not None
        ],
        daily=daily_rows(data),
        location=dict(lat=data.get("latitude"), lon=data.get("longitude")),
    )
