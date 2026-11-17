import { Box, Button, Flex, Grid, Spinner, Text } from "@chakra-ui/react";
import { useContext, useEffect, useRef, useState } from "react";
import HighchartsImport from "highcharts";
import HighchartsMore from "highcharts/highcharts-more";
import useSWR from "swr";
import { unitForObsType } from "../format";
import { fetcher } from "./conf";
import { UnitCtx } from "./Page";
import { fmtRain, StaleNote } from "./forecast";
import { PT, STATION_CHART_TIME, stationAxisDay, stationSharedTooltip } from "./stationTime";

// Ensemble rain totals (GEFS and ECMWF ENS): spread, operational/control, cumulative plume,
// and how the operational total for a fixed valid window has changed across recent runs.

const HC = HighchartsImport.default || HighchartsImport;
if (typeof HC === "object" && typeof window !== "undefined" && HC.seriesTypes && !HC.seriesTypes.arearange) {
  HighchartsMore(HC);
}

function rainConv(unit) {
  return (mm) => (mm == null ? null : (unit === "us" ? mm / 25.4 : mm));
}

export function useEnsemble() {
  const { data, error } = useSWR("/api/forecast/ensemble", fetcher, { refreshInterval: 600000 });
  return { ens: data?.result, error, loading: !data && !error };
}

function TotalsTable({ model, hours, unit }) {
  const w = model.windows && model.windows[String(hours)];
  if (!w) return <Text fontSize="sm" color="gray.600">Totals unavailable.</Text>;
  const row = (label, mm, weight) => (
    <Flex key={label} justify="space-between" fontSize="sm" py="0.5">
      <Text>{label}</Text>
      <Text fontWeight={weight || "normal"} color="blue.700">{mm == null ? "–" : fmtRain(unit, mm, true)}</Text>
    </Flex>
  );
  const spread = (w.p10 != null && w.p90 != null)
    ? fmtRain(unit, w.p10, true) + " – " + fmtRain(unit, w.p90, true)
    : "–";
  return (
    <Box className="ens-totals">
      {row(model.control_label || "Operational", w.control, "bold")}
      {row("Ensemble mean", w.mean, "bold")}
      <Flex justify="space-between" fontSize="sm" py="0.5">
        <Text>10th–90th percentile</Text>
        <Text color="blue.700">{spread}</Text>
      </Flex>
      {row("Lowest member", w.min)}
      {row("Highest member", w.max)}
      <Text fontSize="xs" color="gray.600" mt="1">{w.n} members</Text>
    </Box>
  );
}

const MODEL_COLORS = {
  gefs: {
    main: "#1f6aa5",
    band: "rgba(31,106,165,0.25)",
    member: "rgba(31,106,165,0.14)",
  },
  ecmwf: {
    main: "#c45c16",
    band: "rgba(196,92,22,0.25)",
    member: "rgba(196,92,22,0.14)",
  },
};

function modelColor(key) {
  return MODEL_COLORS[key] || MODEL_COLORS.gefs;
}

function sliceAcc(acc, hours, conv, arr) {
  if (!acc || !acc.times || !acc.times.length || !arr) return [];
  const end = acc.times[0] + hours * 3600 * 1000;
  const last = acc.times.findIndex((t) => t >= end);
  const cut = last < 0 ? arr : arr.slice(0, last + 1);
  return acc.times.slice(0, cut.length).map((t, i) => [t, conv(cut[i])]);
}


function stationMidnightTicks(times) {
  if (!times || !times.length) return undefined;
  const ticks = [];
  let prev = null;
  times.forEach((ms) => {
    const key = new Intl.DateTimeFormat("en-CA", { timeZone: PT, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(ms));
    if (key !== prev) {
      prev = key;
      ticks.push(ms);
    }
  });
  return ticks;
}

function bandAcc(acc, hours, conv) {
  if (!acc || !acc.times || !acc.times.length) return [];
  const end = acc.times[0] + hours * 3600 * 1000;
  const last = acc.times.findIndex((t) => t >= end);
  const xs = last < 0 ? acc.times : acc.times.slice(0, last + 1);
  return xs.map((t, i) => [t, conv((acc.p10 || [])[i]), conv((acc.p90 || [])[i])]);
}

function accumOptions(models, hours, unit) {
  const conv = rainConv(unit);
  const rUnit = unitForObsType(unit, "rain");
  const dec = unit === "us" ? 2 : 1;
  const series = [];
  const keys = ["gefs", "ecmwf"].filter((k) => models[k] && models[k].accumulation && models[k].accumulation.times);
  keys.forEach((key) => {
    const model = models[key];
    const acc = model.accumulation;
    const col = modelColor(key);
    const short = key === "ecmwf" ? "ECMWF" : "GEFS";
    Object.keys(acc.members || {}).slice(0, 50).forEach((name) => {
      series.push({
        name: short + " " + name, type: "line", data: sliceAcc(acc, hours, conv, acc.members[name]),
        color: col.member, lineWidth: 1, enableMouseTracking: false, showInLegend: false, zIndex: 1,
      });
    });
    series.push({
      name: short + " 10th–90th", type: "arearange", data: bandAcc(acc, hours, conv),
      color: col.band, zIndex: 2, fillOpacity: 0.55, tooltip: { valueDecimals: dec, valueSuffix: " " + rUnit },
    });
    series.push({
      name: short + " mean", type: "line", data: sliceAcc(acc, hours, conv, acc.mean),
      color: col.main, lineWidth: 2.25, zIndex: 3, tooltip: { valueDecimals: dec, valueSuffix: " " + rUnit },
    });
    series.push({
      name: model.control_label || (short + " control"), type: "line",
      data: sliceAcc(acc, hours, conv, acc.control),
      color: col.main, lineWidth: 2, dashStyle: "ShortDash", zIndex: 4,
      tooltip: { valueDecimals: dec, valueSuffix: " " + rUnit },
    });
  });
  if (!series.length) return null;
  return {
    chart: { height: 340, backgroundColor: "#ffffff", marginLeft: 56, marginRight: 16, style: { fontFamily: "inherit" }, time: STATION_CHART_TIME },
    title: { text: "Accumulated rain", align: "left", style: { fontSize: "0.9rem", fontWeight: "normal" } },
    credits: { enabled: false },
    legend: { itemStyle: { fontSize: "0.75rem", fontWeight: "normal" } },
    xAxis: {
      type: "datetime", gridLineWidth: 1, gridLineColor: "#eee",
      tickPositions: stationMidnightTicks((models[keys[0]] && models[keys[0]].accumulation && models[keys[0]].accumulation.times) || []),
      labels: { style: { fontSize: "0.72rem" }, formatter: function () { return stationAxisDay(this.value); } },
    },
    yAxis: { title: { text: rUnit, style: { fontSize: "0.75rem" } }, min: 0, gridLineColor: "#eee", labels: { style: { fontSize: "0.72rem" } } },
    tooltip: stationSharedTooltip(),
    plotOptions: { series: { animation: false, marker: { enabled: false } }, arearange: { lineWidth: 0 } },
    series,
  };
}

function runsOptions(models, hours, unit) {
  const rUnit = unitForObsType(unit, "rain");
  const conv = rainConv(unit);
  const series = [];
  const colors = { gefs: MODEL_COLORS.gefs.main, ecmwf: MODEL_COLORS.ecmwf.main };
  Object.entries(models).forEach(([key, model]) => {
    const runs = (model.runs && model.runs[String(hours)]) || [];
    if (!runs.length) return;
    series.push({
      name: model.previous_label || model.name,
      type: "line",
      color: colors[key] || "#333",
      lineWidth: 2,
      marker: { enabled: true, radius: 3 },
      data: runs.map((r) => [-r.lead_days, conv(r.total)]),
    });
  });
  if (!series.length) return null;
  return {
    chart: { height: 280, backgroundColor: "#ffffff", marginLeft: 56, marginRight: 16, style: { fontFamily: "inherit" }, time: STATION_CHART_TIME },
    title: { text: "Operational total across recent runs", align: "left", style: { fontSize: "0.9rem", fontWeight: "normal" } },
    subtitle: { text: "Same valid window; “0” is the latest run, “−1” is about 24 hours earlier", align: "left", style: { fontSize: "0.72rem", color: "#555" } },
    credits: { enabled: false },
    legend: { itemStyle: { fontSize: "0.75rem", fontWeight: "normal" } },
    xAxis: { title: { text: "Days ago", style: { fontSize: "0.75rem" } }, tickInterval: 1, labels: { style: { fontSize: "0.72rem" } }, gridLineWidth: 1, gridLineColor: "#eee" },
    yAxis: { title: { text: rUnit, style: { fontSize: "0.75rem" } }, min: 0, gridLineColor: "#eee", labels: { style: { fontSize: "0.72rem" } } },
    tooltip: { shared: true, valueDecimals: unit === "us" ? 2 : 1, valueSuffix: " " + rUnit, headerFormat: "<span>Run {point.key} day(s) ago</span><br/>" },
    plotOptions: { series: { animation: false } },
    series,
  };
}

function ChartHost({ options, id }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || !options || typeof window === "undefined") return undefined;
    const chart = HC.chart(ref.current, options);
    return () => { try { chart.destroy(); } catch (e) { /* ignore */ } };
  }, [options, id]);
  if (!options) return <Text fontSize="sm" color="gray.600">Chart data unavailable.</Text>;
  return <Box ref={ref} id={id} className="ens-chart" />;
}

export function EnsembleRain() {
  const unit = useContext(UnitCtx);
  const { ens, error, loading } = useEnsemble();
  const [hours, setHours] = useState(168);
  const models = ens && ens.models ? ens.models : {};
  const modelList = ["gefs", "ecmwf"].map((k) => models[k]).filter(Boolean);
  const runsOpts = ens ? runsOptions(models, hours, unit) : null;

  return (
    <Box id="forecast-ensemble" className="forecast-section" border="2px solid #656382" bg="gray.100"
      p={{ base: 2, md: 4 }} borderRadius="10px" mb="6">
      <Text fontSize={{ base: "lg", md: "xl" }} mb="1">Ensemble rain totals</Text>
      <Text fontSize="sm" color="gray.700" mb="3">
        GEFS and ECMWF ensemble forecasts of rainfall at the station. The plume shows every member, the mean,
        the 10th–90th percentile band and the operational (control) run. The run-to-run chart is the operational
        total for a fixed valid window (from this hour through the next 7 or 10 days) as it stood on earlier runs.
      </Text>
      {loading && <Spinner size="sm" />}
      {error && !ens && <Text fontSize="sm" color="gray.600">Ensemble forecasts unavailable right now.</Text>}
      {ens && !modelList.length && <Text fontSize="sm" color="gray.600">Ensemble data is temporarily unavailable.</Text>}
      {ens && modelList.length > 0 && <>
        <Flex className="ens-window-toggle" mb="3" wrap="wrap" align="center" gridGap="2">
          <Text fontSize="sm" fontWeight="semibold" mr="1">Valid window</Text>
          {(ens.windows || [{ hours: 168, label: "Next 7 days" }, { hours: 240, label: "Next 10 days" }]).map((w) => (
            <Button key={w.hours} size="sm" variant={hours === w.hours ? "solid" : "outline"} colorScheme="blue"
              onClick={() => setHours(w.hours)}>{w.label}</Button>
          ))}
        </Flex>
        {ens && <StaleNote stale={ens.stale} fetchedAt={ens.fetched_at} />}
        <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={{ base: 4, md: 6 }} mb="4">
          {modelList.map((m) => (
            <Box key={m.id} className={"ens-model ens-model-" + m.id} bg="white" borderRadius="8px" p="3">
              <Text fontWeight="bold" mb="1">{m.name}</Text>
              <TotalsTable model={m} hours={hours} unit={unit} />
            </Box>
          ))}
        </Grid>
        <Box bg="white" borderRadius="8px" p="3" overflowX="auto" mb="4">
          <ChartHost id={"ens-acc-" + hours} options={accumOptions(models, hours, unit)} />
        </Box>
        <Box bg="white" borderRadius="8px" p="3" overflowX="auto">
          <ChartHost id={"ens-runs-" + hours} options={runsOpts} />
          <Text fontSize="xs" color="gray.600" mt="2">
            Run history comes from Open-Meteo’s previous-runs API (up to 7 days of lead-time offsets for the
            operational GFS seamless and ECMWF IFS 0.25° forecasts). Ensemble member spread is from the latest
            GEFS (30 members + control) and ECMWF ENS (50 members + control) runs.
          </Text>
        </Box>
      </>}
      <Text fontSize="xs" color="gray.600" mt="2">
        Source: <Box as="a" href="https://open-meteo.com/" textDecoration="underline">Open-Meteo</Box> Ensemble and Previous Runs APIs.
      </Text>
    </Box>
  );
}
