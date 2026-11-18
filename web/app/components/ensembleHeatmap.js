import { Box, Button, Flex, Text } from "@chakra-ui/react";
import { useEffect, useRef } from "react";
import HighchartsImport from "highcharts";
import HighchartsHeatmap from "highcharts/modules/heatmap";
import { unitForObsType } from "../format";
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

function rainConv(unit) {
  return (mm) => (mm == null ? null : (unit === "us" ? mm / 25.4 : mm));
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
  const rUnit = unitForObsType(unit, "rain");
  const dec = unit === "us" ? 2 : 1;
  const data = [];
  let max = 0;
  rows.forEach((row, y) => {
    (row.values || []).forEach((v, x) => {
      const yv = conv(v);
      if (yv == null) return;
      data.push([x, y, yv]);
      if (yv > max) max = yv;
    });
  });
  const yCats = rows.map((r) => r.run_label || r.run_z);
  const xCats = cols.map(colLabel);
  const height = Math.max(200, 56 + rows.length * 18 + 48);
  return {
    chart: {
      type: "heatmap",
      height,
      backgroundColor: "#ffffff",
      marginLeft: 88,
      marginRight: 16,
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
    legend: { enabled: false },
    colorAxis: {
      min: 0,
      max: max > 0 ? max : undefined,
      stops: [
        [0, "#fff7ec"],
        [0.15, "#fee8c8"],
        [0.35, "#fdbb84"],
        [0.55, "#e34a33"],
        [0.8, "#b30000"],
        [1, "#7f0000"],
      ],
      labels: { style: { fontSize: "0.7rem" }, formatter: function () { return this.value % 1 === 0 ? this.value : this.value.toFixed(dec); } },
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
        are about 6 days). Colour scale is cumulative amount, not the model colour.
      </Text>
      {show.map((k) => (
        <Box key={k} mb="3" overflowX="auto">
          <ChartHost id={"ens-heat-" + k + "-" + hours} options={heatmapOptions(sliced, k, unit)} />
        </Box>
      ))}
    </Box>
  );
}
