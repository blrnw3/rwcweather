import { dailyNormal } from "./climate";

/**
 * Thresholds for severe-weather badges on the meteogram daily strip.
 * All values are metric (km/h, mm, °C). Tweak these constants; dayAlerts()
 * converts forecast winds from mph and looks up daily climate normals.
 *
 * Defaults are a first pass for the Redwood City hillside site:
 *   - Windy / High wind sit below typical NWS advisory criteria so an
 *     ordinary blustery or stronger storm day is flagged here.
 *   - 15 mm / 30 mm mark a solidly wet day vs a storm-total kind of day.
 *   - Temperature departures are clearly unusual (~+10 °F / −7 °F).
 *   - Frost risk uses a 2 °C screen-level floor (grass frost is likely).
 */
export const SEVERE_WEATHER = {
  WINDY_GUST_KMH: 55,
  WINDY_SUSTAINED_KMH: 35,
  HIGH_WIND_GUST_KMH: 75,
  HIGH_WIND_SUSTAINED_KMH: 50,
  HEAVY_RAIN_MM: 15,
  VERY_HEAVY_RAIN_MM: 30,
  HOT_ABOVE_NORMAL_C: 6,
  COLD_BELOW_NORMAL_C: 4,
  FROST_TMIN_C: 2,
};

const MPH_TO_KMH = 1.60934;

export function mphToKmh(mph) {
  return mph == null ? null : mph * MPH_TO_KMH;
}

export function dailyTempNormals(dateStr) {
  if (!dateStr || typeof dateStr !== "string") return { tmax: null, tmin: null };
  const parts = dateStr.split("-").map(Number);
  if (parts.length < 3 || parts.some((n) => !Number.isFinite(n))) {
    return { tmax: null, tmin: null };
  }
  const [year, month, day] = parts;
  return {
    tmax: dailyNormal("temp", "max", year, month, day),
    tmin: dailyNormal("temp", "min", year, month, day),
  };
}

/**
 * Compact alerts for one daily-strip day. Forecast winds are mph; rain is mm;
 * temps are °C. Returns the strongest matching badge per family, or [].
 */
export function dayAlerts(day) {
  if (!day) return [];
  const T = SEVERE_WEATHER;
  const alerts = [];
  const gustKmh = mphToKmh(day.gust_max);
  const windKmh = mphToKmh(day.wind_max);
  const highWind =
    (gustKmh != null && gustKmh >= T.HIGH_WIND_GUST_KMH) ||
    (windKmh != null && windKmh >= T.HIGH_WIND_SUSTAINED_KMH);
  const windy =
    (gustKmh != null && gustKmh >= T.WINDY_GUST_KMH) ||
    (windKmh != null && windKmh >= T.WINDY_SUSTAINED_KMH);
  if (highWind) {
    alerts.push({
      key: "high-wind",
      label: "High wind",
      shortLabel: "Wind+",
      tone: "wind-high",
      gustKmh,
      windKmh,
    });
  } else if (windy) {
    alerts.push({
      key: "windy",
      label: "Windy",
      shortLabel: "Windy",
      tone: "wind",
      gustKmh,
      windKmh,
    });
  }

  const rain = day.precip != null ? day.precip : day.rain_mm;
  if (rain != null && rain >= T.VERY_HEAVY_RAIN_MM) {
    alerts.push({ key: "very-heavy-rain", label: "Very heavy rain", shortLabel: "Very wet", tone: "rain-heavy", rainMm: rain });
  } else if (rain != null && rain >= T.HEAVY_RAIN_MM) {
    alerts.push({ key: "heavy-rain", label: "Heavy rain", shortLabel: "Heavy rain", tone: "rain", rainMm: rain });
  }

  const normals = dailyTempNormals(day.date);
  const tmax = day.tmax;
  const tmin = day.tmin;
  if (tmax != null && normals.tmax != null && tmax >= normals.tmax + T.HOT_ABOVE_NORMAL_C) {
    alerts.push({
      key: "hot",
      label: "Hot",
      shortLabel: "Hot",
      tone: "hot",
      tmax,
      normalTmax: normals.tmax,
    });
  }
  if (tmin != null && tmin <= T.FROST_TMIN_C) {
    alerts.push({
      key: "frost",
      label: "Frost risk",
      shortLabel: "Frost",
      tone: "frost",
      tmin,
      normalTmin: normals.tmin,
    });
  } else if (tmin != null && normals.tmin != null && tmin <= normals.tmin - T.COLD_BELOW_NORMAL_C) {
    alerts.push({
      key: "cold",
      label: "Cold",
      shortLabel: "Cold",
      tone: "cold",
      tmin,
      normalTmin: normals.tmin,
    });
  }
  return alerts;
}
