import { Box, Button, Flex, Text } from "@chakra-ui/react";
import { useEffect, useRef } from "react";
import HighchartsImport from "highcharts";
import HighchartsHeatmap from "highcharts/modules/heatmap";
import { fmtRain } from "./forecast";
import { STATION_CHART_TIME } from "./stationTime";

// Cumulative rain heatmap: rows are operational model cycles (newest at the
// top), columns are 6-hourly valid times in Pacific. SSR-safe Highcharts
// import; the heatmap module is registered only in the browser.

const HC = HighchartsImport.default || HighchartsImport;
if (typeof HC === "object" && typeof window !== "undefined" && HC.seriesTypes && !HC.seriesTypes.heatmap) {
  const factory = HighchartsHeatmap.default || HighchartsHeatmap;
  if (typeof factory === "function") factory(HC);
}

const MODEL_COLORS = {
  gfs: "#c2185b",
  ecmwf: "#1f6aa5",
};

const MODEL_NAMES = {
  gfs: "GFS seamless",
  ecmwf: "ECMWF IFS",
};

// Fixed cumulative-rain colour scale in millimetres. Stops are [mm, colour].
// The axis is always 0–100 mm (converted in US inches mode); values above
// 100 mm clamp to the final purple. Not data-relative.
export const HEATMAP_MAX_MM = 100;
export const HEATMAP_COLOR_STOPS_MM = [
  [0, "#deebf7"],    // light blue
  [20, "#9ecae1"],
  [35, "#4292c6"],
  [49, "#08519c"],   // darker blue just under 50 mm
  [50, "#fdae6b"],   // orange at/above 50 mm
  [65, "#f16913"],
  [80, "#de2d26"],   // reds
  [92, "#a50f15"],
  [100, "#7a0177"],  // purple at 100 mm and above
];

function rainConv(unit) {
  return (mm) => (mm == null ? null : (unit === "us" ? mm / 25.4 : mm));
}

function colorAxisStops() {
  return HEATMAP_COLOR_STOPS_MM.map(([mm, color]) => [mm / HEATMAP_MAX_MM, color]);
}

export function sliceHeatmap(heat, hours) {
  if (!heat || !heat.columns) return heat;
  const start = Date.parse(heat.start);
  if (!isFinite(start) || !hours) return heat;
  const end = start + hours * 3600 * 1000;
  const keep = [];
  heat.columns.forEach((c, i) => { if (c.t <= end) keep.push(i); });
  if (keep.length === heat.columns.length) return heat;
  const columns = keep.map((i) => heat.columns[i]);
  const models = {};
  Object.keys(heat.models || {}).forEach((key) => {
    models[key] = (heat.models[key] || []).map((row) => ({
      ...row,
      values: keep.map((i) => (row.values || [])[i]),
    }));
  });
  return { ...heat, columns, models, hours };
}

function colLabel(c) {
  return c.label || "";
}

function heatmapOptions(heat, modelKey, unit) {
  const rows = (heat.models && heat.models[modelKey]) || [];
  const cols = heat.columns || [];
  if (!rows.length || !cols.length) return null;
  const conv = rainConv(unit);
  const data = [];
  rows.forEach((row, y) => {
    (row.values || []).forEach((v, x) => {
      const yv = conv(v);
      if (yv == null) return;
      data.push([x, y, yv]);
    });
  });
  const yCats = rows.map((r) => r.run_label || r.run_z);
  const xCats = cols.map(colLabel);
  const height = Math.max(200, 56 + rows.length * 18 + 48);
  const axisMax = conv(HEATMAP_MAX_MM);
  const tickMm = [0, 25, 50, 75, 100];
  return {
    chart: {
      type: "heatmap",
      height,
      backgroundColor: "#ffffff",
      marginLeft: 88,
      marginRight: 64,
      marginBottom: 72,
      style: { fontFamily: "inherit" },
      time: STATION_CHART_TIME,
    },
    title: {
      text: MODEL_NAMES[modelKey] + " cumulative rain by run",
      align: "left",
      style: { fontSize: "0.9rem", fontWeight: "normal", color: MODEL_COLORS[modelKey] || "#333" },
    },
    credits: { enabled: false },
    legend: {
      enabled: true,
      layout: "vertical",
      align: "right",
      verticalAlign: "middle",
      symbolHeight: 240,
      symbolWidth: 14,
      y: 10,
      itemStyle: { fontSize: "0.7rem", fontWeight: "normal" },
    },
    colorAxis: {
      min: 0,
      max: axisMax,
      startOnTick: false,
      endOnTick: false,
      stops: colorAxisStops(),
      tickPositions: tickMm.map(conv),
      labels: {
        style: { fontSize: "0.7rem" },
        formatter: function () {
          const mm = unit === "us" ? this.value * 25.4 : this.value;
          return fmtRain(unit, mm, true);
        },
      },
    },
    xAxis: {
      categories: xCats,
      opposite: false,
      labels: {
        rotation: -55,
        style: { fontSize: "0.65rem" },
        step: cols.length > 24 ? 2 : 1,
      },
      tickWidth: 0,
    },
    yAxis: {
      categories: yCats,
      title: { text: null },
      reversed: true, // category 0 is newest; Highcharts puts index 0 at the bottom unless reversed
      labels: { style: { fontSize: "0.72rem" } },
    },
    tooltip: {
      formatter: function () {
        const row = rows[this.point.y] || {};
        const col = cols[this.point.x] || {};
        const val = this.point.value;
        const txt = val == null ? "–" : fmtRain(unit, unit === "us" ? val * 25.4 : val, true);
        return "<b>" + (MODEL_NAMES[modelKey] || modelKey) + " " + (row.run_label || "") + " UTC</b><br/>"
          + "Valid " + (col.label || "") + "<br/>"
          + "Cumulative: <b>" + (txt || "–") + "</b>";
      },
    },
    plotOptions: { series: { animation: false, borderWidth: 0, colsize: 1, rowsize: 1 } },
    series: [{
      type: "heatmap",
      name: MODEL_NAMES[modelKey],
      data,
      dataLabels: { enabled: false },
      turboThreshold: 0,
      nullColor: "#f0f0f0",
    }],
    // Keep the fixed colour bar off the cells on narrow screens: sit it under the x labels.
    responsive: {
      rules: [{
        condition: { maxWidth: 540 },
        chartOptions: {
          chart: { marginRight: 12, marginBottom: 150, height: height + 72 },
          legend: {
            layout: "horizontal",
            align: "center",
            verticalAlign: "bottom",
            symbolWidth: 240,
            symbolHeight: 14,
            y: 28,
          },
          colorAxis: {
            tickPositions: [0, conv(50), conv(100)],
            labels: { style: { fontSize: "0.65rem" }, y: 14 },
          },
        },
      }],
    },
  };
}

function ChartHost({ options, id }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || !options || typeof window === "undefined") return undefined;
    const chart = HC.chart(ref.current, options);
    return () => { try { chart.destroy(); } catch (e) { /* ignore */ } };
  }, [options, id]);
  if (!options) return <Text fontSize="sm" color="gray.600">Heatmap data unavailable.</Text>;
  return <Box ref={ref} id={id} className="ens-heatmap-chart" />;
}

export function EnsembleHeatmap({ heat, hours, unit, view, onView }) {
  const sliced = sliceHeatmap(heat, hours);
  const keys = ["gfs", "ecmwf"].filter((k) => sliced && sliced.models && (sliced.models[k] || []).length);
  const show = view === "both" ? keys : keys.filter((k) => k === view);
  if (!keys.length) {
    return <Text fontSize="sm" color="gray.600">Run heatmap unavailable.</Text>;
  }
  return (
    <Box className="ens-heatmap">
      <Flex mb="2" wrap="wrap" align="center" gridGap="2">
        <Text fontSize="sm" fontWeight="semibold" mr="1">Heatmap</Text>
        {[{ id: "both", label: "Both models" }, { id: "gfs", label: "GFS" }, { id: "ecmwf", label: "ECMWF" }].map((b) => (
          <Button key={b.id} size="sm"
            variant={view === b.id ? "solid" : "outline"}
            colorScheme={b.id === "ecmwf" ? "blue" : (b.id === "gfs" ? "pink" : "gray")}
            onClick={() => onView(b.id)}>{b.label}</Button>
        ))}
      </Flex>
      <Text fontSize="xs" color="gray.600" mb="2">
        Cumulative rain from this hour, by operational model cycle (newest at the top) and 6-hourly
        valid time in Pacific Time. Grey cells are past a short cycle&apos;s forecast horizon (ECMWF 06z/18z
        are about 6 days). The colour scale is fixed at 0–100 mm (clamped above 100 mm; the same
        thresholds in inches in US units), not relative to the data or the model colour.
      </Text>
      {show.map((k) => (
        <Box key={k} mb="3" overflowX="auto">
          <ChartHost id={"ens-heat-" + k + "-" + hours} options={heatmapOptions(sliced, k, unit)} />
        </Box>
      ))}
    </Box>
  );
}
