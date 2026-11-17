// Station-local clock for forecast charts. Highcharts defaults to time.useUTC=true, so its
// dateFormat / xDateFormat would show UTC hours (8 h ahead of Pacific in winter). All visible
// times on the forecast page use America/Los_Angeles, independent of the viewer's browser zone.
import { PT } from "./forecast";

export { PT };

function parts(ms, options) {
  return new Intl.DateTimeFormat("en-US", { timeZone: PT, ...options }).formatToParts(new Date(ms));
}

function grab(list, type) {
  const p = list.find((x) => x.type === type);
  return p ? p.value : "";
}

export function stationAxisDay(ms) {
  const p = parts(ms, { weekday: "short", day: "numeric" });
  return grab(p, "weekday") + " " + grab(p, "day");
}

export function stationTooltipTime(ms) {
  const p = parts(ms, {
    weekday: "short", day: "numeric", month: "short",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
  return grab(p, "weekday") + " " + grab(p, "day") + " " + grab(p, "month") + " "
    + grab(p, "hour") + ":" + grab(p, "minute");
}

export function stationHour(ms) {
  const p = parts(ms, { hour: "numeric", hourCycle: "h23" });
  return Number(grab(p, "hour"));
}

// Highcharts time options: keep instants in UTC internally; never use the browser zone.
export const STATION_CHART_TIME = { useUTC: true };

export function stationSharedTooltip() {
  return {
    shared: true,
    style: { fontSize: "0.75rem" },
    formatter: function () {
      const pts = this.points || (this.point ? [this] : []);
      if (!pts.length) return false;
      let html = stationTooltipTime(this.x);
      pts.forEach((p) => {
        if (p.series && p.series.options && p.series.options.enableMouseTracking === false) return;
        const tip = (p.series && p.series.tooltipOptions) || {};
        const suffix = tip.valueSuffix != null ? tip.valueSuffix : "";
        const dec = tip.valueDecimals;
        if (p.point && p.point.low != null && p.point.high != null) {
          const lo = dec != null ? Number(p.point.low).toFixed(dec) : p.point.low;
          const hi = dec != null ? Number(p.point.high).toFixed(dec) : p.point.high;
          html += "<br/>" + p.series.name + ": <b>" + lo + "</b> – <b>" + hi + "</b>" + suffix;
          return;
        }
        if (p.y == null) return;
        const y = dec != null ? Number(p.y).toFixed(dec) : p.y;
        html += "<br/><span style=\"color:" + (p.color || "#333") + "\">\u25CF</span> "
          + p.series.name + ": <b>" + y + "</b>" + suffix;
      });
      return html;
    },
  };
}
