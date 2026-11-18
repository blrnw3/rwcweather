import { Box, Button, Flex, Text } from "@chakra-ui/react";
import { useEffect, useRef } from "react";
import HighchartsImport from "highcharts";
import HighchartsHeatmap from "highcharts/modules/heatmap";
import { fmtRain, fmtWhen } from "./forecast";
import { STATION_CHART_TIME } from "./stationTime";

// Cumulative rain heatmaps. SSR-safe Highcharts import; the heatmap module
// is registered only in the browser.

const HC = HighchartsImport.default || HighchartsImport;
if (typeof HC === "object" && typeof window !== "undefined" && HC.seriesTypes && !HC.seriesTypes.heatmap) {
  const factory = HighchartsHeatmap.default || HighchartsHeatmap;
  if (typeof factory === "function") factory(HC);
}

const MODEL_COLORS = {
  gfs: "#c2185b",
  gefs: "#c2185b",
  ecmwf: "#1f6aa5",
};

const MODEL_NAMES = {
  gfs: "GFS seamless",
  gefs: "GEFS",
  ecmwf: "ECMWF IFS",
};

// Fixed cumulative-rain scale in millimetres. These are discrete dataClasses
// (not interpolated stops): RGB interpolation between the dark-blue 50 mm
// edge and the orange just above it passed through muddy grey, which showed
// up as isolated "missing" cells mid-row when a column landed near 50 mm.
export const HEATMAP_MAX_MM = 100;
export const HEATMAP_DATA_CLASSES_MM = [
  { from: 0, color: "#deebf7" },    // light blue
  { from: 20, color: "#9ecae1" },
  { from: 35, color: "#08519c" },   // darker blue up to 50
  { from: 50, color: "#fdae6b" },   // orange at/above 50 mm
  { from: 65, color: "#f16913" },
  { from: 80, color: "#de2d26" },   // reds
  { from: 92, color: "#a50f15" },
  { from: 100, color: "#7a0177" },  // purple at 100 mm and above
];
// Kept as an alias of the class edges so callers can still talk about "stops".
export const HEATMAP_COLOR_STOPS_MM = HEATMAP_DATA_CLASSES_MM.map((c) => [c.from, c.color]);

const NULL_COLOR = "#d0d0d0";
const NULL_TOOLTIP = "No data past this run's forecast horizon";

function rainConv(unit) {
  return (mm) => (mm == null ? null : (unit === "us" ? mm / 25.4 : mm));
}

function dataClasses(unit) {
  const conv = rainConv(unit);
  const n = HEATMAP_DATA_CLASSES_MM.length;
  return HEATMAP_DATA_CLASSES_MM.map((c, i) => {
    const next = HEATMAP_DATA_CLASSES_MM[i + 1];
    const from = conv(c.from);
    const to = next ? conv(next.from) : undefined;
    const fmt = (mm) => (unit === "us" ? (mm / 25.4).toFixed(2).replace(/\.00$/, "") + " in" : String(mm) + " mm");
    const name = i === n - 1 ? (fmt(c.from) + "+") : (fmt(c.from) + "–" + fmt(next.from));
    return { from, to, color: c.color, name };
  });
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
    const block = heat.models[key];
    // Run heatmap: models[key] is a row array. Member heatmap: { rows, ... }.
    if (Array.isArray(block)) {
      models[key] = block.map((row) => ({
        ...row,
        values: keep.map((i) => (row.values || [])[i]),
      }));
    } else if (block && Array.isArray(block.rows)) {
      models[key] = {
        ...block,
        rows: block.rows.map((row) => ({
          ...row,
          values: keep.map((i) => (row.values || [])[i]),
        })),
      };
    } else {
      models[key] = block;
    }
  });
  return { ...heat, columns, models, hours };
}


function lastTotal(values) {
  if (!values || !values.length) return null;
  for (let i = values.length - 1; i >= 0; i -= 1) {
    if (values[i] != null) return values[i];
  }
  return null;
}

function sortRowsWettest(rows) {
  return (rows || []).slice().sort((a, b) => {
    const ta = lastTotal(a.values);
    const tb = lastTotal(b.values);
    if (ta == null && tb == null) return String(a.id || "").localeCompare(String(b.id || ""));
    if (ta == null) return 1;
    if (tb == null) return -1;
    if (tb !== ta) return tb - ta;
    return String(a.id || "").localeCompare(String(b.id || ""));
  });
}

function colLabel(c) {
  return c.label || "";
}

function heatmapOptions({ rows, cols, unit, title, titleColor, compact, yLabel, nullTooltip }) {
  if (!rows || !rows.length || !cols || !cols.length) return null;
  const conv = rainConv(unit);
  const data = [];
  rows.forEach((row, y) => {
    (row.values || []).forEach((v, x) => {
      const yv = conv(v);
      // Always emit a point, including null, so nullColor grey shows instead of a white gap.
      data.push({ x, y, value: yv == null ? null : yv });
    });
  });
  const yCats = rows.map((r) => yLabel ? yLabel(r) : (r.run_label || r.label || r.run_z || r.id));
  const xCats = cols.map(colLabel);
  const rowH = compact ? 11 : 18;
  const labelSize = compact ? "0.58rem" : "0.72rem";
  const marginLeft = compact ? 72 : 88;
  const height = Math.max(240, (compact ? 44 : 56) + rows.length * rowH + 110);
  return {
    chart: {
      type: "heatmap",
      height,
      backgroundColor: "#ffffff",
      marginLeft,
      marginRight: 16,
      marginBottom: 120,
      style: { fontFamily: "inherit" },
      time: STATION_CHART_TIME,
    },
    title: {
      text: title || "",
      align: "left",
      style: { fontSize: compact ? "0.82rem" : "0.9rem", fontWeight: "normal", color: titleColor || "#333" },
    },
    credits: { enabled: false },
    legend: {
      enabled: true,
      layout: "horizontal",
      align: "center",
      verticalAlign: "bottom",
      itemDistance: 10,
      itemStyle: { fontSize: "0.65rem", fontWeight: "normal" },
      symbolRadius: 0,
      symbolHeight: 10,
      symbolWidth: 14,
      y: 24,
    },
    colorAxis: {
      dataClasses: dataClasses(unit),
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
      reversed: true,
      labels: {
        style: { fontSize: labelSize },
        useHTML: true,
        formatter: function () {
          const text = String(this.value);
          const row = rows[this.pos] || rows.find((r) => (r.label || r.run_label) === this.value);
          if (row && row.is_control) return "<b>" + text + "</b>";
          return text;
        },
      },
    },
    tooltip: {
      formatter: function () {
        const row = rows[this.point.y] || {};
        const col = cols[this.point.x] || {};
        const val = this.point.value;
        if (val == null) {
          return "<b>" + (yLabel ? yLabel(row) : (row.run_label || row.label || "")) + "</b><br/>"
            + "Valid " + (col.label || "") + "<br/>" + (nullTooltip || NULL_TOOLTIP);
        }
        const txt = fmtRain(unit, unit === "us" ? val * 25.4 : val, true);
        return "<b>" + (yLabel ? yLabel(row) : (row.run_label || row.label || "")) + "</b><br/>"
          + "Valid " + (col.label || "") + "<br/>"
          + "Cumulative: <b>" + (txt || "–") + "</b>";
      },
    },
    plotOptions: { series: { animation: false, borderWidth: 0, colsize: 1, rowsize: 1 } },
    series: [{
      type: "heatmap",
      data,
      dataLabels: { enabled: false },
      turboThreshold: 0,
      nullColor: NULL_COLOR,
      borderColor: "#ffffff",
      borderWidth: compact ? 0 : 0,
    }],
    responsive: {
      rules: [{
        condition: { maxWidth: 540 },
        chartOptions: {
          chart: { marginLeft: compact ? 56 : 86, marginBottom: 140, height: height + 20 },
          legend: { itemDistance: 6, itemStyle: { fontSize: "0.6rem", fontWeight: "normal" } },
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

function ModelToggle({ view, onView, options }) {
  return (
    <Flex mb="2" wrap="wrap" align="center" gridGap="2">
      {options.map((b) => (
        <Button key={b.id} size="sm"
          variant={view === b.id ? "solid" : "outline"}
          colorScheme={b.colorScheme}
          onClick={() => onView(b.id)}>{b.label}</Button>
      ))}
    </Flex>
  );
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
        <ModelToggle view={view} onView={onView} options={[
          { id: "both", label: "Both models", colorScheme: "gray" },
          { id: "gfs", label: "GFS", colorScheme: "pink" },
          { id: "ecmwf", label: "ECMWF", colorScheme: "blue" },
        ]} />
      </Flex>
      <Text fontSize="xs" color="gray.600" mb="2">
        Cumulative rain from this hour, by operational model cycle (newest at the top) and 6-hourly
        valid time in Pacific Time. Grey cells are past a short cycle&apos;s forecast horizon (ECMWF 06z/18z
        are about 6 days). The colour scale is fixed at 0–100 mm in discrete bands (clamped above 100 mm;
        the same thresholds in inches in US units), not relative to the data or the model colour.
      </Text>
      {show.map((k) => (
        <Box key={k} mb="3" overflowX="auto">
          <ChartHost id={"ens-heat-" + k + "-" + hours}
            options={heatmapOptions({
              rows: sliced.models[k],
              cols: sliced.columns,
              unit,
              title: MODEL_NAMES[k] + " cumulative rain by run",
              titleColor: MODEL_COLORS[k],
              nullTooltip: NULL_TOOLTIP,
            })} />
        </Box>
      ))}
    </Box>
  );
}

function memberTitle(block, fetchedAt) {
  const short = (block && block.short) || "";
  const run = block && block.run;
  if (run && (run.run_label || run.run_z)) {
    return short + " " + (run.run_label || run.run_z) + " UTC — members, wettest at the top";
  }
  const when = fmtWhen(fetchedAt);
  return short + " members, wettest at the top"
    + (when ? " (init not published; fetched " + when + ")" : " (init not published)");
}

export function EnsembleMemberHeatmap({ heat, hours, unit, view, onView, fetchedAt }) {
  const sliced = sliceHeatmap(heat, hours);
  const keys = ["gefs", "ecmwf"].filter((k) => {
    const b = sliced && sliced.models && sliced.models[k];
    return b && (b.rows || []).length;
  });
  const show = view === "both" ? keys : keys.filter((k) => k === view);
  if (!keys.length) {
    return <Text fontSize="sm" color="gray.600">Ensemble-member heatmap unavailable.</Text>;
  }
  return (
    <Box className="ens-member-heatmap" mt="4">
      <Flex mb="2" wrap="wrap" align="center" gridGap="2">
        <Text fontSize="sm" fontWeight="semibold" mr="1">Ensemble members</Text>
        <ModelToggle view={view} onView={onView} options={[
          { id: "both", label: "Both models", colorScheme: "gray" },
          { id: "gefs", label: "GEFS", colorScheme: "pink" },
          { id: "ecmwf", label: "ECMWF ENS", colorScheme: "blue" },
        ]} />
      </Flex>
      <Text fontSize="xs" color="gray.600" mb="2">
        One row per member of the latest ensemble run (GEFS control + 30, ECMWF ENS control + 50),
        sorted by each member&apos;s final cumulative total over the selected window, wettest at the top.
        The control row is labelled in bold. Columns and the 0–100 mm colour scale match the run heatmap
        above. Built from the ensemble payload already on the page — no extra upstream requests.
      </Text>
      {show.map((k) => {
        const block = sliced.models[k];
        const rows = sortRowsWettest(block.rows || []);
        return (
          <Box key={k} mb="3" overflowX="auto">
            <ChartHost id={"ens-member-heat-" + k + "-" + hours}
              options={heatmapOptions({
                rows,
                cols: sliced.columns,
                unit,
                title: memberTitle(block, fetchedAt),
                titleColor: MODEL_COLORS[k],
                compact: true,
                yLabel: (r) => r.label,
                nullTooltip: NULL_TOOLTIP,
              })} />
          </Box>
        );
      })}
    </Box>
  );
}
