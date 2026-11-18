import { Box, Spinner, Text } from "@chakra-ui/react";
import { useContext, useEffect, useRef, useState } from "react";
import HighchartsImport from "highcharts";
import {
  WiCloudy, WiDayCloudy, WiDaySunny, WiFog, WiRain, WiRainWind, WiShowers,
  WiSprinkle, WiStrongWind, WiThunderstorm,
} from "react-icons/wi";
import useSWR from "swr";
import { convFunction, unitForObsType } from "../format";
import { fetcher } from "./conf";
import { UnitCtx } from "./Page";
import { fmtRain, StaleNote, UpdateLine } from "./forecast";
import { dayAlerts } from "./forecastDayAlerts";
import { STATION_CHART_TIME, sortedUniquePoints, stationAxisDay, stationSharedTooltip } from "./stationTime";

// Stacked 10-day meteogram, modelled on nw3weather's forecast page: a per-day
// summary strip aligned to each day's span on the chart, then panels for
// temperature & dew point, precipitation, cloud, wind & gusts, and pressure.
// Charts are created only in the browser (Highcharts touches `window`).
// Day icons are Weather Icons by Erik Flowers (SIL Open Font License), the same
// set already used on the home page via react-icons/wi.

const HC = HighchartsImport.default || HighchartsImport;

const COLORS = {
  temp: "#d34f00",
  dew: "#0b8043",
  precip: "#2554c7",
  pop: "rgba(37,84,199,0.28)",
  cloud: "#5a7a9a",
  wind: "#c01717",
  gust: "#c23b86",
  pressure: "#5b3fb0",
};

const WINDY_MPH = 25;

// Meteogram number formatting. Metric rain is 1 dp; wind, gust and pressure
// (mb) are 0 dp. US inches and inHg keep 2 dp (0 dp would be unusable).
function meteogramDecimals(unit, kind) {
  if (kind === "rain") return unit === "us" ? 2 : 1;
  if (kind === "pres") return unit === "us" ? 2 : 0;
  if (kind === "wind" || kind === "gust") return 0;
  return 1;
}

function axisDecimalsFormatter(decimals) {
  return function () {
    const n = Number(this.value);
    if (!Number.isFinite(n)) return "";
    if (decimals === 0) return String(Math.round(n));
    if (Number.isInteger(n) || Math.abs(n - Math.round(n)) < 1e-9) return String(Math.round(n));
    return n.toFixed(decimals);
  };
}

const ALERT_TONE = {
  "wind-high": { bg: "#9b2c2c", color: "#fff" },
  wind: { bg: "#c05621", color: "#fff" },
  "rain-heavy": { bg: "#2a4365", color: "#fff" },
  rain: { bg: "#2b6cb0", color: "#fff" },
  hot: { bg: "#c53030", color: "#fff" },
  frost: { bg: "#2c5282", color: "#fff" },
  cold: { bg: "#4c6b8a", color: "#fff" },
};

function alertTitle(a) {
  const bits = [];
  if (a.gustKmh != null) bits.push("gusts " + Math.round(a.gustKmh) + " km/h");
  if (a.windKmh != null) bits.push("sustained " + Math.round(a.windKmh) + " km/h");
  if (a.rainMm != null) bits.push(a.rainMm.toFixed(1) + " mm");
  if (a.tmax != null && a.normalTmax != null) {
    bits.push("high " + a.tmax.toFixed(1) + "°C vs normal " + a.normalTmax.toFixed(1) + "°C");
  }
  if (a.tmin != null) {
    bits.push("low " + a.tmin.toFixed(1) + "°C" + (a.normalTmin != null ? " vs normal " + a.normalTmin.toFixed(1) + "°C" : ""));
  }
  return a.label + (bits.length ? ": " + bits.join(", ") : "");
}

function fmtStripWind(unit, mph, withUnit) {
  if (mph == null) return null;
  const n = Math.round(convFunction(unit, "wind")(mph));
  return withUnit === false ? String(n) : (n + " " + unitForObsType(unit, "wind"));
}


const DAY_ICONS = {
  sunny: WiDaySunny,
  partlycloudy: WiDayCloudy,
  cloudy: WiCloudy,
  fog: WiFog,
  drizzle: WiSprinkle,
  rain: WiRain,
  heavyrain: WiRainWind,
  showers: WiShowers,
  thunder: WiThunderstorm,
  wind: WiStrongWind,
};

export function iconForDay(day) {
  const n = day && day.weather_code != null && day.weather_code !== ""
    ? Number(day.weather_code) : null;
  let key = null;
  let label = (day && day.weather) || "Conditions";
  if (n === 0 || n === 1) key = "sunny";
  else if (n === 2) key = "partlycloudy";
  else if (n === 3) key = "cloudy";
  else if (n === 45 || n === 48) key = "fog";
  else if (n >= 51 && n <= 57) key = "drizzle";
  else if (n === 61 || n === 63 || n === 66) key = "rain";
  else if (n === 65 || n === 67 || n === 82) key = "heavyrain";
  else if (n === 80 || n === 81 || n === 85 || n === 86) key = "showers";
  else if (n === 95 || n === 96 || n === 99) key = "thunder";
  else if (n >= 71 && n <= 77) key = "rain";
  if (!key && day) {
    const p = day.precip;
    if (p >= 15) { key = "heavyrain"; label = "Heavy rain"; }
    else if (p >= 2) { key = "rain"; label = "Rain"; }
    else if (p > 0) { key = "drizzle"; label = "Light rain"; }
    else key = "cloudy";
  }
  if (!key) key = "cloudy";
  const windy = day && day.wind_max != null && day.wind_max >= WINDY_MPH;
  if (windy && (key === "sunny" || key === "partlycloudy" || key === "cloudy")) {
    key = "wind";
    label = (label && label !== "Conditions" ? label + ", windy" : "Windy");
  }
  return { key, label, Icon: DAY_ICONS[key] || WiCloudy };
}

function DayIcon({ day, size }) {
  const { Icon, label } = iconForDay(day);
  return (
    <Box as="span" title={label} role="img" aria-label={label} lineHeight="1"
      color="gray.700" display="inline-flex">
      <Icon size={size} aria-hidden="true" />
    </Box>
  );
}

function dayLabelShort(d, tight) {
  const raw = d.label || d.date || "";
  const parts = raw.split(/\s+/);
  if (tight) return parts[0] || raw;
  if (parts.length >= 2) return parts[0] + " " + parts[1];
  return raw;
}

export function computeDayCols(chart, daily) {
  if (!chart || !chart.xAxis || !chart.xAxis[0] || !daily || !daily.length) return [];
  const axis = chart.xAxis[0];
  const min = axis.min;
  const max = axis.max;
  if (!isFinite(min) || !isFinite(max) || max <= min) return [];
  const out = [];
  daily.forEach((d) => {
    const start = d.start;
    const end = d.end != null ? d.end : (start + 24 * 3600 * 1000);
    if (start == null || end <= min || start >= max) return;
    const t0 = Math.max(start, min);
    const t1 = Math.min(end, max);
    const left = axis.toPixels(t0, false);
    const right = axis.toPixels(t1, false);
    const width = right - left;
    if (!isFinite(left) || !isFinite(width) || width < 2) return;
    out.push({
      date: d.date,
      left,
      width,
      narrow: width < 72,
      tight: width < 44,
      day: d,
    });
  });
  return out;
}

function DailyStrip({ cols, unit }) {
  if (!cols || !cols.length) return null;
  const tUnit = unitForObsType(unit, "temp");
  const toTemp = convFunction(unit, "temp");
  const alertsByI = cols.map((c) => dayAlerts(c.day));
  const maxAlerts = alertsByI.reduce((m, a) => Math.max(m, a.length), 0);
  const baseH = { base: 90, md: 92 };
  const h = { base: `${baseH.base + maxAlerts * 14}px`, md: `${baseH.md + maxAlerts * 14}px` };
  return (
    <Box className="fc-mg-daystrip" position="relative" h={h} mb="0"
      fontSize="11px" color="gray.800" borderBottom="1px solid #ddd">
      {cols.map((c, i) => {
        const d = c.day;
        const hi = d.tmax != null ? Math.round(toTemp(d.tmax)) : null;
        const lo = d.tmin != null ? Math.round(toTemp(d.tmin)) : null;
        const rain = d.precip != null ? fmtRain(unit, d.precip, true) : null;
        const wind = fmtStripWind(unit, d.wind_max, true);
        const gustNum = fmtStripWind(unit, d.gust_max, false);
        const iconSize = c.tight ? 18 : (c.narrow ? 24 : 30);
        const alerts = alertsByI[i];
        return (
          <Box key={d.date} className="fc-mg-daycol" position="absolute" top="0" bottom="0"
            left={c.left + "px"} width={c.width + "px"}
            textAlign="center" overflow="hidden" px="1px"
            borderLeft="1px solid #d8d8d8"
            display="flex" flexDir="column" alignItems="center" justifyContent="flex-start"
            pt="2px">
            <Text fontWeight="semibold" fontSize={c.tight ? "9px" : "11px"} lineHeight="1.2"
              whiteSpace="nowrap" title={d.label}>
              {dayLabelShort(d, c.tight)}
            </Text>
            <DayIcon day={d} size={iconSize} />
            <Text lineHeight="1.25" whiteSpace="nowrap" title={"High / low " + tUnit}>
              {hi != null
                ? <Text as="span" color="red.700">{hi}°</Text>
                : "–"}
              {!c.tight && lo != null
                ? <Text as="span"> / <Text as="span" color="blue.700">{lo}°</Text></Text>
                : null}
            </Text>
            {!c.tight && (
              <Text lineHeight="1.25" color="blue.700" whiteSpace="nowrap"
                title={rain ? rain + (d.pop != null ? " · " + d.pop + "% chance" : "") : ""}>
                {rain || "–"}
                {d.pop != null && !c.narrow ? <Text as="span" color="gray.600"> · {d.pop}%</Text> : null}
                {d.pop != null && c.narrow ? <Text as="span" color="gray.600"> {d.pop}%</Text> : null}
              </Text>
            )}
            {!c.narrow && wind && (
              <Text lineHeight="1.2" color="gray.700" whiteSpace="nowrap"
                title={wind + (gustNum ? " gust " + gustNum : "")}>
                {wind}{gustNum ? <Text as="span" color="gray.500"> g{gustNum}</Text> : null}
              </Text>
            )}
            {alerts.map((a) => {
              const tone = ALERT_TONE[a.tone] || ALERT_TONE.wind;
              const text = c.tight || c.narrow ? (a.shortLabel || a.label) : a.label;
              return (
                <Text
                  key={a.key}
                  className="fc-mg-day-alert"
                  title={alertTitle(a)}
                  fontSize="9px"
                  fontWeight="semibold"
                  lineHeight="1.2"
                  px="1"
                  mt="0.5"
                  borderRadius="sm"
                  bg={tone.bg}
                  color={tone.color}
                  maxW="100%"
                  isTruncated
                >
                  {text}
                </Text>
              );
            })}
          </Box>
        );
      })}
    </Box>
  );
}

function convertSeries(points, conv) {
  if (!points) return [];
  return points.map((pt) => {
    const x = Array.isArray(pt) ? pt[0] : pt.x;
    const y = Array.isArray(pt) ? pt[1] : pt.y;
    if (y == null) return [x, null];
    return [x, conv(y)];
  });
}

function rainConv(unit) {
  const toDisplay = convFunction(unit, "rain");
  return (mm) => toDisplay(mm / 25.4);
}

export function useMeteogram() {
  const { data, error } = useSWR("/api/forecast/meteogram", fetcher, { refreshInterval: 600000 });
  return { mg: data?.result, error, loading: !data && !error };
}

function axisRange(seriesList) {
  let min = Infinity, max = -Infinity;
  seriesList.forEach((s) => (s || []).forEach((pt) => {
    const x = Array.isArray(pt) ? pt[0] : pt && pt.x;
    if (x == null) return;
    if (x < min) min = x;
    if (x > max) max = x;
  }));
  if (!isFinite(min)) return { min: undefined, max: undefined };
  const now = Date.now();
  if (now < max) min = Math.min(min, now);
  return { min, max };
}

function nowAnnot(withLabel, xMin, xMax) {
  const now = Date.now();
  const bands = [];
  if (isFinite(xMin) && now > xMin) {
    bands.push({
      from: xMin, to: isFinite(xMax) ? Math.min(now, xMax) : now,
      color: "rgba(40, 48, 56, 0.08)", zIndex: 1,
    });
  }
  return {
    plotBands: bands,
    plotLines: [{
      value: now, color: "#5a5a5a", width: 1, zIndex: 7,
      label: withLabel ? {
        text: "now", rotation: 0, align: "left", verticalAlign: "bottom", x: 3, y: -4,
        style: { color: "#555", fontSize: "10px", fontWeight: "normal" },
      } : { text: null },
    }],
  };
}

function localMidnightTicks(daily, xMin, xMax) {
  if (!isFinite(xMin) || !isFinite(xMax) || !daily) return [];
  return daily
    .map((d) => d.start)
    .filter((t) => t != null && t >= xMin && t <= xMax);
}

function buildCharts(el, series, unit) {
  const HCAPI = HC;
  const tConv = convFunction(unit, "temp");
  const rConv = rainConv(unit);
  const wConv = convFunction(unit, "wind");
  const pConv = convFunction(unit, "pres");
  const tUnit = unitForObsType(unit, "temp");
  const rUnit = unitForObsType(unit, "rain");
  const wUnit = unitForObsType(unit, "wind");
  const pUnit = unitForObsType(unit, "pres");

  const temp = sortedUniquePoints(convertSeries(series.temp, tConv));
  const dew = sortedUniquePoints(convertSeries(series.dew, tConv));
  const precip = sortedUniquePoints(convertSeries(series.precip, rConv));
  const pop = sortedUniquePoints(series.pop || []);
  const cloud = sortedUniquePoints(series.cloud || []);
  const wind = sortedUniquePoints(convertSeries(series.wind, wConv));
  const gust = sortedUniquePoints(convertSeries(series.gust, wConv));
  const pressure = sortedUniquePoints(convertSeries(series.pressure, pConv));
  const { min: xMin, max: xMax } = axisRange([temp, dew, precip, wind, gust, pressure, cloud, pop]);

  const ticks = localMidnightTicks(series.daily, xMin, xMax);

  el.innerHTML = ["temp", "precip", "cloud", "wind", "pres"].map(
    (id) => `<div class="fc-mg-panel" id="${el.id}-${id}"></div>`
  ).join("");

  const xCommon = {
    type: "datetime",
    min: xMin,
    max: xMax,
    minPadding: 0,
    maxPadding: 0,
    tickPositions: ticks.length ? ticks : undefined,
    startOnTick: false,
    endOnTick: false,
    ordinal: false,
    crosshair: true,
    gridLineWidth: 1,
    gridLineColor: "#cccccc",
    dateTimeLabelFormats: { hour: "%H", day: "%a %e" },
    labels: {
      autoRotation: false,
      style: { fontSize: "0.72rem" },
      formatter: function () { return stationAxisDay(this.value); },
    },
  };
  const rainDp = meteogramDecimals(unit, "rain");
  const windDp = meteogramDecimals(unit, "wind");
  const presDp = meteogramDecimals(unit, "pres");
  const baseChart = {
    backgroundColor: "#ffffff",
    marginLeft: 56,
    marginRight: 48,
    spacing: [6, 10, 4, 8],
    style: { fontFamily: "inherit" },
    time: STATION_CHART_TIME,
  };
  const tip = stationSharedTooltip();

  const charts = [];
  function panel(suffix, height, yAxis, seriesOpts, xLabels, title) {
    const annot = nowAnnot(suffix === "temp", xMin, xMax);
    const tightTop = suffix === "temp";
    charts.push(HCAPI.chart(el.id + "-" + suffix, {
      chart: { ...baseChart, height, spacing: tightTop ? [2, 10, 4, 8] : baseChart.spacing },
      title: { text: title, align: "left", margin: tightTop ? 2 : 6, style: { fontSize: "0.85rem", fontWeight: "normal", color: "#333" } },
      credits: { enabled: false },
      legend: { enabled: seriesOpts.length > 1, align: "right", verticalAlign: "top", floating: true, itemStyle: { fontSize: "0.72rem", fontWeight: "normal" } },
      xAxis: { ...xCommon, ...annot, labels: { ...xCommon.labels, enabled: !!xLabels }, tickLength: xLabels ? 4 : 0, lineWidth: xLabels ? 1 : 0 },
      yAxis,
      tooltip: tip,
      plotOptions: {
        series: { animation: false, marker: { enabled: false }, states: { inactive: { opacity: 1 } } },
        column: { borderWidth: 0, pointPadding: 0.05, groupPadding: 0.05, pointRange: 3600 * 1000 },
        areaspline: { fillOpacity: 1, lineWidth: 0 },
      },
      series: seriesOpts,
    }));
  }

  panel("temp", 170, [
    { title: { text: tUnit, style: { color: COLORS.temp, fontSize: "0.75rem" } }, labels: { style: { color: COLORS.temp, fontSize: "0.72rem" } }, gridLineColor: "#eee", opposite: false },
  ], [
    { name: "Temperature", type: "spline", data: temp, color: COLORS.temp, lineWidth: 2, tooltip: { valueDecimals: 1, valueSuffix: " " + tUnit } },
    { name: "Dew point", type: "spline", data: dew, color: COLORS.dew, lineWidth: 1.5, tooltip: { valueDecimals: 1, valueSuffix: " " + tUnit } },
  ], false, "Temperature and dew point");

  panel("precip", 160, [
    { title: { text: rUnit, style: { color: COLORS.precip, fontSize: "0.75rem" } }, labels: { style: { color: COLORS.precip, fontSize: "0.72rem" }, formatter: axisDecimalsFormatter(rainDp) }, min: 0, gridLineColor: "#eee", softMax: rConv(1) },
    { title: { text: "%", style: { color: COLORS.precip, fontSize: "0.75rem" } }, labels: { style: { color: "#2554c7", fontSize: "0.72rem" } }, min: 0, max: 100, opposite: true, gridLineWidth: 0 },
  ], [
    { name: "Rain chance", type: "spline", data: pop, color: "rgba(37,84,199,0.55)", lineWidth: 1.5, dashStyle: "ShortDash", yAxis: 1, tooltip: { valueSuffix: "%" }, zIndex: 1 },
    { name: "Precipitation", type: "column", data: precip, color: COLORS.precip, tooltip: { valueDecimals: rainDp, valueSuffix: " " + rUnit }, zIndex: 2 },
  ], false, "Precipitation");

  panel("cloud", 130, [
    { title: { text: "%", style: { color: COLORS.cloud, fontSize: "0.75rem" } }, labels: { style: { color: COLORS.cloud, fontSize: "0.72rem" } }, min: 0, max: 100, gridLineColor: "#eee" },
  ], [
    { name: "Cloud cover", type: "areaspline", data: cloud, color: COLORS.cloud, tooltip: { valueSuffix: "%" } },
  ], false, "Cloud cover");

  panel("wind", 160, [
    { title: { text: wUnit, style: { color: COLORS.wind, fontSize: "0.75rem" } }, labels: { style: { color: COLORS.wind, fontSize: "0.72rem" }, formatter: axisDecimalsFormatter(windDp) }, min: 0, softMax: 5, gridLineColor: "#eee" },
  ], [
    { name: "Wind", type: "spline", data: wind, color: COLORS.wind, lineWidth: 1.75, tooltip: { valueDecimals: windDp, valueSuffix: " " + wUnit } },
    { name: "Gusts", type: "spline", data: gust, color: COLORS.gust, lineWidth: 1.25, dashStyle: "ShortDash", tooltip: { valueDecimals: windDp, valueSuffix: " " + wUnit } },
  ], false, "Wind");

  panel("pres", 140, [
    { title: { text: pUnit, style: { color: COLORS.pressure, fontSize: "0.75rem" } }, labels: { style: { color: COLORS.pressure, fontSize: "0.72rem" }, formatter: axisDecimalsFormatter(presDp) }, gridLineColor: "#eee" },
  ], [
    { name: "Pressure", type: "spline", data: pressure, color: COLORS.pressure, lineWidth: 1.75, tooltip: { valueDecimals: presDp, valueSuffix: " " + pUnit } },
  ], true, "Pressure");

  return charts;
}

export function Meteogram() {
  const unit = useContext(UnitCtx);
  const { mg, error, loading } = useMeteogram();
  const hostRef = useRef(null);
  const innerRef = useRef(null);
  const chartsRef = useRef([]);
  const [cols, setCols] = useState([]);

  useEffect(() => {
    chartsRef.current.forEach((c) => { try { c.destroy(); } catch (e) { /* already gone */ } });
    chartsRef.current = [];
    setCols([]);
    const el = hostRef.current;
    const series = mg && mg.series;
    if (!el || !series || !series.temp || !series.temp.length) return undefined;
    if (typeof window === "undefined") return undefined;
    chartsRef.current = buildCharts(el, series, unit);

    let raf = 0;
    const layout = () => {
      const chart = chartsRef.current[0];
      if (!chart) return;
      setCols(computeDayCols(chart, series.daily || []));
    };
    const layoutSoon = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(layout);
    };
    const unbind = chartsRef.current.map((c) => HC.addEvent(c, "redraw", layoutSoon));
    const inner = innerRef.current;
    let ro = null;
    let lastW = 0;
    const onResizeSafe = () => {
      const w = inner ? inner.clientWidth : 0;
      if (w && w !== lastW) {
        lastW = w;
        chartsRef.current.forEach((c) => { try { c.reflow(); } catch (e) { /* ignore */ } });
      }
      layoutSoon();
    };
    if (inner && typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(onResizeSafe);
      ro.observe(inner);
    }
    window.addEventListener("resize", onResizeSafe);
    raf = requestAnimationFrame(layout);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResizeSafe);
      if (ro) ro.disconnect();
      unbind.forEach((fn) => { try { fn(); } catch (e) { /* ignore */ } });
      chartsRef.current.forEach((c) => { try { c.destroy(); } catch (e) { /* ignore */ } });
      chartsRef.current = [];
    };
  }, [mg, unit]);

  return (
    <Box id="forecast-meteogram" className="forecast-section" border="2px solid #656382" bg="gray.100"
      p={{ base: 2, md: 4 }} borderRadius="10px" mb="6">
      <Text fontSize={{ base: "lg", md: "xl" }} mb="1">10-day meteogram</Text>
      <Text fontSize="sm" color="gray.700" mb="3">
        Hourly temperature and dew point, precipitation amount and chance, cloud cover, wind and gusts, and pressure
        at the station (37.470, −122.265, ~125 m). Data: Open-Meteo GFS seamless (HRRR in the near term, GFS thereafter).
      </Text>
      {mg && <UpdateLine fetchedAt={mg.fetched_at} modelRun={mg.model_run} stale={mg.stale}
        note={mg.model_run ? "Near-term hours may include later HRRR updates." : null} />}
      {loading && <Spinner size="sm" />}
      {error && !mg && <Text fontSize="sm" color="gray.600">Meteogram unavailable right now.</Text>}
      {mg && !mg.series && <Text fontSize="sm" color="gray.600">Meteogram data is temporarily unavailable.</Text>}
      <Box className="fc-mg-scroll" overflowX="auto">
        <Box ref={innerRef} className="fc-mg-scroll-inner" minW={{ base: "960px", md: "100%" }}>
          {mg && mg.series && <DailyStrip cols={cols} unit={unit} />}
          <Box ref={hostRef} id="fc-meteogram-charts" className="fc-meteogram-stack" />
        </Box>
      </Box>
      <Text fontSize="xs" color="gray.600" mt="1" display={{ base: "block", md: "none" }}>
        Swipe the charts sideways to see the full 10 days.
      </Text>
      <Text fontSize="xs" color="gray.600" mt="2">
        Source: <Box as="a" href="https://open-meteo.com/" textDecoration="underline">Open-Meteo</Box>
        {mg && mg.model_note ? " · " + mg.model_note : null}
      </Text>
    </Box>
  );
}
