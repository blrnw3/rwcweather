import { Box } from "@chakra-ui/react";
import Highcharts from "highcharts";
import HighchartsMore from "highcharts/highcharts-more";
import HighchartsReact from "highcharts-react-official";
import { useContext } from "react";
import useSWR from "swr";
import { convFunction, toFixedObs, unitAndPrecisionForObsType } from "../format";
import { dailyNormal, hasClimate } from "./climate";
import { fetcher, fmatAggTypeOpt, fmatForObs, OBS } from "./conf";
import { yAxisScale } from "./chart";
import { UnitCtx } from "./Page";

// arearange (the all-years band) lives in highcharts-more; it touches `window`, so only initialise it in the browser.
if (typeof Highcharts === "object" && typeof window !== "undefined" && !Highcharts.seriesTypes.arearange) {
    HighchartsMore(Highcharts);
}

// Full-year daily time series against the daily climate normal (/charts/year),
// modelled on nw3weather's year-to-date "cumulative trends" charts (wx12 / wx14).
// Values from the API and data/climate.js are in DB units; converted here.

const MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAY_MS = 86400000;

function ymd(t) {
    const d = new Date(t);
    return [d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate()];
}
const stamp = ([y, m, d]) => "" + y + String(m).padStart(2, "0") + String(d).padStart(2, "0");

/** First and last day (UTC ms) of the calendar year, or of water year `year` (1 Oct year-1 .. 30 Sep year). */
export function periodBounds(year, waterYear) {
    return waterYear
        ? [Date.UTC(year - 1, 9, 1), Date.UTC(year, 8, 30)]
        : [Date.UTC(year, 0, 1), Date.UTC(year, 11, 31)];
}

/** Daily normal in DB units; sunshine % of possible is derived from the sunshine and max-possible normals. */
export function normalFor(obs, stat, y, m, d) {
    if (obs === "sunpct") {
        const sun = dailyNormal("sun", "total", y, m, d);
        const possible = dailyNormal("sun", "possible", y, m, d);
        return sun != null && possible ? 100 * sun / possible : null;
    }
    if (obs === "sun") {
        return smoothDailyTotal(obs, stat, y, m, d);
    }
    return dailyNormal(obs, stat, y, m, d);
}

const daysIn = (y, m) => new Date(Date.UTC(y, m, 0)).getUTCDate();

/**
 * Daily sunshine normal: there is no daily sun normal, so take each month's
 * hours per day (monthly / days in month) and interpolate between mid-months,
 * avoiding steps at month boundaries (day length changes smoothly).
 */
function smoothDailyTotal(obs, stat, y, m, d) {
    const perDay = (yy, mm) => {
        const total = dailyNormal(obs, stat, yy, mm, 1);
        return total == null ? null : total;  // dailyNormal for totals = monthly / days in month
    };
    if (perDay(y, m) == null) {
        return null;
    }
    const t = Date.UTC(y, m - 1, d) + DAY_MS / 2;
    const mid = (yy, mm) => Date.UTC(yy, mm - 1, 1) + daysIn(yy, mm) * DAY_MS / 2;
    let [y0, m0] = t < mid(y, m) ? (m === 1 ? [y - 1, 12] : [y, m - 1]) : [y, m];
    let [y1, m1] = m0 === 12 ? [y0 + 1, 1] : [y0, m0 + 1];
    const f = (t - mid(y0, m0)) / (mid(y1, m1) - mid(y0, m0));
    return perDay(y0, m0) + f * (perDay(y1, m1) - perDay(y0, m0));
}

export function hasNormal(obs, stat) {
    return obs === "sunpct" ? hasClimate("sun", "total") && hasClimate("sun", "possible") : hasClimate(obs, stat);
}

function isMobile() {
    return typeof window !== "undefined" && window.innerWidth < 768;
}
const fontSize = (base) => Math.round(base * (isMobile() ? 0.75 : 1)) + "px";

export function useYearDaily(obs, stat, year, waterYear, enabled = true) {
    const [start, end] = periodBounds(year, waterYear);
    const url = !enabled ? null : "/api/var/daily/" + obs + "/" + stat + "/?include_today=1&start=" + stamp(ymd(start)) + "&end=" + stamp(ymd(end));
    const { data, error } = useSWR(url, fetcher, { refreshInterval: 300000, revalidateOnFocus: false });
    return { result: data?.result, server: data?.server, error, isLoading: !!url && !data && !error };
}

// All-years statistics per calendar day (wind direction is circular and a fog day is 0/1, so neither has them).
const NO_DAY_STATS = ["wdir", "fogday"];
export const hasDayStats = (obs) => !NO_DAY_STATS.includes(obs);

// The "All" year is drawn on a leap year's calendar so 29 Feb has its place; Oct-Dec of a water year fall in 2023.
export const ALL_YEARS_REF = 2024;

/** All-years avg / min / max for each calendar day: running-total envelopes when cumulative. DB units. */
export function useDayStats(obs, stat, cumulative, waterYear, enabled = true) {
    const q = cumulative ? "?mode=cumulative" + (waterYear ? "&period=water" : "") : "";
    const url = enabled && hasDayStats(obs) ? "/api/var/day_stats/" + obs + "/" + stat + "/" + q : null;
    const { data, error } = useSWR(url, fetcher, { refreshInterval: 0, revalidateOnFocus: false });
    const byDay = data?.result ? new Map(data.result.map((r) => [r.m * 100 + r.d, r])) : null;
    return { byDay, error, isLoading: enabled && !!url && !data && !error };
}

/**
 * Build the observed and normal series (DB units) for every day of the period.
 * Observed days missing from the API are null (gaps). In cumulative mode both
 * become running totals; the observed total stops after the last reported day.
 */
export function buildSeries(rows, obs, stat, year, waterYear, cumulative, dayStats = null) {
    const [start, end] = periodBounds(year, waterYear);
    const byDay = new Map((rows || []).map((r) => [stamp(r.d), r.val]));
    let lastObs = -1;
    const days = [];
    for (let t = start; t <= end; t += DAY_MS) {
        const [y, m, d] = ymd(t);
        const v = byDay.get(stamp([y, m, d]));
        if (v != null) {
            lastObs = days.length;
        }
        // all-years stats are already running totals in cumulative mode (from the API), so they are not summed here
        days.push({ t, obs: v ?? null, normal: normalFor(obs, stat, y, m, d), stats: dayStats?.get(m * 100 + d) || null });
    }
    if (cumulative) {
        let run = 0, runN = 0;
        days.forEach((day, i) => {
            run += day.obs ?? 0;
            runN += day.normal ?? 0;
            day.obs = i <= lastObs ? run : null;
            day.normal = runN;
        });
    }
    return days;
}

const round = (v, p) => (v == null ? null : Number(v.toFixed(p)));

export function YearChart({ obs, stat, year, waterYear, cumulative, showNormal, today, height, spacing,
    showStats = false, allYears = false }) {
    // Optional height / spacing override for embedded uses (e.g. homepage); defaults match /charts/year.
    // showStats overlays the all-years avg (dashed) and lowest-highest band for each calendar day; allYears draws
    // only those, on a reference leap year's calendar.

    const unit = useContext(UnitCtx);
    const fmat = fmatForObs(obs, stat);
    const { unitSymbol, precision } = unitAndPrecisionForObsType(unit, fmat);
    const conv = convFunction(unit, fmat);
    if (allYears) {
        year = ALL_YEARS_REF;
    }
    const statsOn = (showStats || allYears) && hasDayStats(obs);
    const { result, isLoading: obsLoading } = useYearDaily(obs, stat, year, waterYear, !allYears);
    const { byDay: dayStats, isLoading: statsLoading } = useDayStats(obs, stat, cumulative, waterYear, statsOn);
    const isLoading = obsLoading || statsLoading;
    const normalOk = !allYears && showNormal && hasNormal(obs, stat);
    const days = buildSeries(result, obs, stat, year, waterYear, cumulative, statsOn ? dayStats : null);
    const prec = cumulative ? Math.max(precision, 0) : precision;
    const c = (v) => (v == null ? null : round(conv(v), prec));
    const isTotal = OBS.get(obs).summary === "total";
    const name = OBS.get(obs).name + (isTotal || obs === "sunpct" ? "" : " (" + fmatAggTypeOpt(stat).toLowerCase() + ")");
    const period = allYears ? (waterYear ? "All water years" : "All years") : waterYear ? "Water year " + (year - 1) + "–" + String(year).slice(2) : String(year);
    const color = obs === "rain" ? "#2299dd" : obs === "wet" ? "#1f6fae" : obs.startsWith("rain") ? "#2299dd" : obs.startsWith("sun") ? "#e6a700" : stat === "min" ? "#3377dd" : "#ff5511";
    const columns = !cumulative && isTotal;

    // in "All" mode today's month/day is marked on the reference calendar
    const todayT = !today ? null : !allYears ? Date.UTC(today[0], today[1] - 1, today[2])
        : Date.UTC(waterYear && today[1] >= 10 ? year - 1 : year, today[1] - 1, today[2]);
    const plotLines = today ? [{
        value: todayT, color: "#454332", width: 1.5, dashStyle: "Dash", zIndex: 4,
        label: { text: "Today", rotation: 0, y: 14, x: 4, style: { fontSize: fontSize(12) } },
    }] : [];

    const series = [];
    if (statsOn) {
        // Behind everything: a light band from the lowest to the highest value on each calendar day, thin edges.
        series.push({
            id: "range", type: "arearange", name: "All-years lowest–highest", color, fillOpacity: allYears ? 0.22 : 0.12,
            lineWidth: 0.75, marker: { enabled: false }, zIndex: 0, enableMouseTracking: true,
            data: days.map((d) => ({ x: d.t, low: c(d.stats?.min), high: c(d.stats?.max), minYear: d.stats?.min_year,
                maxYear: d.stats?.max_year })),
        });
    }
    if (!allYears) {
        series.push({
            id: "obs", type: columns ? "column" : "line",
            name: (cumulative ? "Cumulative " + name.toLowerCase() : name),
            color, lineWidth: 2, marker: { enabled: false }, zIndex: 2,
            pointPadding: 0, groupPadding: 0, borderWidth: 0,
            data: days.map((d) => [d.t, c(d.obs)]),
        });
    }
    if (statsOn) {
        series.push({
            id: "avg", type: "line", name: "All-years average", color: allYears ? color : Highcharts.color(color).brighten(-0.4).get(), dashStyle: "Dash",
            lineWidth: allYears ? 2 : 1.25, marker: { enabled: false }, zIndex: 3,
            data: days.map((d) => ({ x: d.t, y: c(d.stats?.avg), n: d.stats?.n })),
        });
    }
    if (normalOk) {
        series.push({
            id: "normal", type: "line", name: cumulative ? "Cumulative normal" : "Normal", color: "#555", dashStyle: cumulative ? "Solid" : "ShortDash",
            lineWidth: 1.5, marker: { enabled: false }, zIndex: 3,
            data: days.map((d) => [d.t, c(d.normal)]),
        });
    }
    const yValues = days.flatMap((d) => [c(d.obs), c(d.normal), c(d.stats?.min), c(d.stats?.max)]);

    const options = {
        credits: { href: null, text: "@rwcweather" },
        chart: {
            height: height != null ? height : (isMobile() ? 360 : 460),
            spacing: spacing != null ? spacing : (isMobile() ? [8, 2, 10, 0] : [15, 15, 15, 10]),
            backgroundColor: isLoading ? "#00000022" : "#fff", zoomType: "x",
        },
        title: {
            text: (isLoading ? "LOADING: " : "") + period + (cumulative ? " cumulative " : " daily ") + name.toLowerCase(),
            style: { fontSize: fontSize(18) },
        },
        time: { useUTC: true },
        legend: { itemStyle: { fontSize: fontSize(12) } },
        xAxis: {
            type: "datetime", crosshair: true, plotLines,
            min: periodBounds(year, waterYear)[0], max: periodBounds(year, waterYear)[1],
            dateTimeLabelFormats: { month: "%b", year: "%b" },
            labels: { formatter() { return MONTH_SHORT[new Date(this.value).getUTCMonth()]; } },
        },
        // #83 rules (chart.yAxisScale): amounts start at 0, levels autoscale (never below 0 for wind/humidity/AQI);
        // auto is null, never undefined
        yAxis: { title: { text: OBS.get(obs).name + " / " + unitSymbol, style: { fontSize: fontSize(13) } }, ...yAxisScale(obs, yValues) },
        tooltip: {
            shared: true, xDateFormat: "%a %e %b %Y", valueDecimals: prec, valueSuffix: " " + unitSymbol,
            formatter() {
                const pts = this.points || [];
                const o = pts.find((p) => p.series.options.id === "obs")?.y;
                const n = pts.find((p) => p.series.options.id === "normal")?.y;
                const v = (x) => "<b>" + toFixedObs(fmat, x, prec) + " " + unitSymbol + "</b>";
                let s = Highcharts.dateFormat(allYears ? "%e %b" : "%a %e %b %Y", this.x);
                pts.forEach((p) => {
                    const dot = "<br/><span style=\"color:" + p.color + "\">●</span> ";
                    const id = p.series.options.id;
                    if (id === "range") {
                        if (p.point.low != null) {
                            s += dot + "All-years lowest: " + v(p.point.low) + " (" + p.point.minYear + ")" +
                                dot + "All-years highest: " + v(p.point.high) + " (" + p.point.maxYear + ")";
                        }
                    } else if (id === "avg") {
                        s += dot + p.series.name + ": " + v(p.y) + (p.point.n ? " (" + p.point.n + " yrs)" : "");
                    } else {
                        s += dot + p.series.name + ": " + v(p.y);
                    }
                });
                if (o != null && n != null) {
                    const diff = o - n;
                    s += "<br/>Anomaly: <b>" + (diff >= 0 ? "+" : "") + toFixedObs(fmat, diff, prec) + " " + unitSymbol + "</b>";
                    if (isTotal && n > 0) {
                        s += " (" + Math.round(100 * o / n) + "% of normal)";
                    }
                }
                return s;
            },
        },
        plotOptions: { series: { animation: false }, column: { grouping: false } },
        series,
    };
    return <Box id="year-chart">
        {/* Remount when the chart's shape changes (series type / count): updating a column chart in place
            into a line chart can throw "reading 'stacks'" inside Highcharts. */}
        <HighchartsReact key={[obs, stat, year, waterYear, cumulative, normalOk, statsOn, allYears].join("|")} highcharts={Highcharts}
            options={options} immutable={true} />
    </Box>;
}
