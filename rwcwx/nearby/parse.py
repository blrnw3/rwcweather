"""Shape nearby-station payloads into a common record (no I/O; unit-tested with fixtures).

Output units: temperatures in °C, rain in mm (the frontend converts to the visitor's unit choice).
"""
import math
import re
from datetime import datetime, timezone
from typing import List, Optional

RWC_LAT, RWC_LON = 37.470, -122.265
RWC_ELEV_M = 125


def f_to_c(f: Optional[float]) -> Optional[float]:
    return None if f is None else round((f - 32) * 5 / 9, 2)


def in_to_mm(inches: Optional[float]) -> Optional[float]:
    return None if inches is None else round(inches * 25.4, 3)


def haversine_km(lat: float, lon: float, lat0: float = RWC_LAT, lon0: float = RWC_LON) -> float:
    r = 6371.0
    p1, l1, p2, l2 = (math.radians(x) for x in (lat0, lon0, lat, lon))
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


def _num(val) -> Optional[float]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, bool) or (isinstance(val, float) and math.isnan(val)):
            return None
        return float(val)
    if isinstance(val, str):
        s = val.strip().replace(",", "")
        if s in ("", "--", "—", "N/A", "n/a"):
            return None
        try:
            return float(s)
        except ValueError:
            return None
    if isinstance(val, dict) and "value" in val:
        return _num(val.get("value"))
    return None


def _iso(ts: Optional[str]) -> Optional[str]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return None


def _from_unix(ts) -> Optional[str]:
    n = _num(ts)
    if n is None or n <= 0:
        return None
    if n > 1e12:      # milliseconds
        n = n / 1000.0
    try:
        return datetime.fromtimestamp(n, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (OSError, OverflowError, ValueError):
        return None


# ---------------------------------------------------------------- official (NWS + IEM)

def nws_temp_c(props: Optional[dict]) -> Optional[float]:
    if not props:
        return None
    t = props.get("temperature") or {}
    val, unit = t.get("value") if isinstance(t, dict) else None, (t.get("unitCode") or "") if isinstance(t, dict) else ""
    n = _num(val)
    if n is None:
        return None
    if unit.endswith("degF") or unit.endswith(":F"):
        return f_to_c(n)
    return round(n, 2)      # NWS official obs are °C


def nws_rain_mm(props: Optional[dict]) -> Optional[float]:
    """Prefer last-24h, then 6h, then 3h, then 1h — only when NWS actually sends a value (often it does not)."""
    if not props:
        return None
    for key in ("precipitationLast24Hours", "precipitationLast6Hours", "precipitationLast3Hours",
                "precipitationLastHour"):
        n = _num((props.get(key) or {}).get("value") if isinstance(props.get(key), dict) else props.get(key))
        if n is not None:
            return round(n, 2)      # NWS precip is mm
    return None


def iem_temp_c(ob: Optional[dict]) -> Optional[float]:
    return f_to_c(_num((ob or {}).get("airtemp[F]")))


def iem_rain_mm(ob: Optional[dict]) -> Optional[float]:
    return in_to_mm(_num((ob or {}).get("precip_today[in]")))


def official(nws: Optional[dict], iem: Optional[dict]) -> Optional[dict]:
    """Temperature prefers the NWS latest observation; today's rain prefers IEM (NWS latest rarely includes it)."""
    temp = nws_temp_c(nws)
    temp_src = "nws" if temp is not None else None
    if temp is None:
        temp = iem_temp_c(iem)
        temp_src = "iem" if temp is not None else None
    rain = iem_rain_mm(iem)
    rain_src = "iem" if rain is not None else None
    if rain is None:
        rain = nws_rain_mm(nws)
        rain_src = "nws" if rain is not None else None
    # Today's (station-local calendar day) extremes: IEM max_dayairtemp / min_dayairtemp.
    # NWS latest has maxTemperatureLast24Hours, which is a rolling 24 h window, so it is not used.
    tmin = f_to_c(_num((iem or {}).get("min_dayairtemp[F]")))
    tmax = f_to_c(_num((iem or {}).get("max_dayairtemp[F]")))
    observed = _iso((nws or {}).get("timestamp")) or _iso((iem or {}).get("utc_valid"))
    if temp is None and rain is None and observed is None and tmin is None and tmax is None:
        return None
    return dict(temp_c=temp, rain_today_mm=rain, observed_at=observed,
                temp_min_c=tmin, temp_max_c=tmax,
                temp_source=temp_src, rain_source=rain_src,
                hilo_source="iem" if (tmin is not None or tmax is not None) else None)


# ---------------------------------------------------------------- WeatherLink

_UNIT_F = re.compile(r"°\s*F|&deg;\s*F|\bF\b", re.I)
_UNIT_C = re.compile(r"°\s*C|&deg;\s*C|\bC\b", re.I)


def weatherlink(data: Optional[dict]) -> Optional[dict]:
    if not data:
        return None
    temp = _num(data.get("temperature"))
    unit = str(data.get("temperatureUnit") or "")
    if temp is not None:
        if _UNIT_C.search(unit) and not _UNIT_F.search(unit):
            temp_c = round(temp, 2)
        else:
            temp_c = f_to_c(temp)      # WeatherLink map JSON is °F
    else:
        temp_c = None
    rain = in_to_mm(_num(data.get("dailyRain")))
    observed = _from_unix(data.get("lastTimestamp"))
    if temp_c is None and rain is None and observed is None:
        return None
    return dict(temp_c=temp_c, rain_today_mm=rain, observed_at=observed,
                temp_min_c=None, temp_max_c=None, hilo_source=None,
                temp_source="weatherlink", rain_source="weatherlink")


def _wl_temp(value, unit) -> Optional[float]:
    n = _num(value)
    if n is None:
        return None
    unit = str(unit or "")
    if _UNIT_C.search(unit) and not _UNIT_F.search(unit):
        return round(n, 2)
    return f_to_c(n)


def weatherlink_hilo(summary: Optional[dict]) -> dict:
    """Today's high and low from a WeatherLink embeddable summary (highLowValues). Map JSON has neither."""
    out = dict(temp_min_c=None, temp_max_c=None, hilo_source=None)
    if not summary:
        return out
    by = {}
    for item in summary.get("highLowValues") or []:
        name = (item or {}).get("sensorDataName")
        if name:
            by[name] = item
    hi, lo = by.get("High Temp") or {}, by.get("Low Temp") or {}
    # Unit is on the value row; default °F like the map JSON.
    unit = hi.get("unitLabel") or lo.get("unitLabel") or "°F"
    out["temp_max_c"] = _wl_temp(hi.get("value"), unit)
    out["temp_min_c"] = _wl_temp(lo.get("value"), unit)
    if out["temp_min_c"] is not None or out["temp_max_c"] is not None:
        out["hilo_source"] = "weatherlink"
    return out


def apply_hilo(obs: Optional[dict], hilo: Optional[dict]) -> Optional[dict]:
    if not obs:
        return obs
    if hilo:
        obs["temp_min_c"] = hilo.get("temp_min_c")
        obs["temp_max_c"] = hilo.get("temp_max_c")
        obs["hilo_source"] = hilo.get("hilo_source")
    return obs


# ---------------------------------------------------------------- station list

# elev_source: "published" from the operator or an official metadata record; "estimated" from Open-Meteo
# terrain elevation at the published coordinates (used only when the operator does not publish one).
STATIONS: List[dict] = [
    dict(id="pulgas", name="Pulgas Ridge", kind="official",
         nws_id="PUGC1", iem_id="PUGC1", iem_network="CA_DCP",
         lat=37.47500, lon=-122.29810, elev_m=198, elev_source="published",
         url="https://www.mesonet.agron.iastate.edu/sites/site.php?network=CA_DCP&station=PUGC1"),
    dict(id="sfo", name="SFO", kind="official",
         nws_id="KSFO", iem_id="SFO", iem_network="CA_ASOS",
         lat=37.61961, lon=-122.36558, elev_m=3, elev_source="published",
         url="https://api.weather.gov/stations/KSFO"),
    dict(id="tum_suden", name="Tum Suden", kind="weatherlink",
         wl_id="d0933c67-011f-4c30-82a8-2095a9ac411d",
         lat=37.45412, lon=-122.26759, elev_m=220, elev_source="estimated",
         url="https://www.weatherlink.com/map/d0933c67-011f-4c30-82a8-2095a9ac411d"),
    dict(id="white_oaks", name="White Oaks", kind="weatherlink",
         wl_id="0ac92eea-e7f3-4837-871e-7220e344bb69",
         lat=37.49107, lon=-122.25648, elev_m=17, elev_source="estimated",
         url="https://www.weatherlink.com/map/0ac92eea-e7f3-4837-871e-7220e344bb69"),
    dict(id="jasper_ridge", name="Jasper Ridge", kind="weatherlink",
         wl_id="a9fe5e92-cdc0-408d-9885-5d69fe378110",
         lat=37.40312, lon=-122.24429, elev_m=128, elev_source="published",
         url="https://www.weatherlink.com/map/a9fe5e92-cdc0-408d-9885-5d69fe378110",
         # Public embed token from the preserve's Weather Resources page; the map JSON has no daily hi/lo.
         wl_embed="f1628dfa80d64cce8825eb59f4020acb"),
]


def meta(st: dict) -> dict:
    return dict(id=st["id"], name=st["name"], url=st["url"], lat=st["lat"], lon=st["lon"],
                elev_m=st["elev_m"], elev_source=st["elev_source"],
                dist_km=haversine_km(st["lat"], st["lon"]))


def station_record(st: dict, obs: Optional[dict]) -> dict:
    rec = meta(st)
    rec.update(temp_c=None, rain_today_mm=None, temp_min_c=None, temp_max_c=None,
               observed_at=None, available=False, temp_source=None, rain_source=None, hilo_source=None)
    if obs:
        rec.update(obs)
        rec["available"] = obs.get("temp_c") is not None or obs.get("rain_today_mm") is not None
    return rec
