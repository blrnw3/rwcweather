import { Box } from "@chakra-ui/react";
import Highcharts from "highcharts";
import HighchartsReact from "highcharts-react-official";
import { useContext } from "react";
import useSWR from "swr";
import { convFunction, unitAndPrecisionForObsType } from "../format";
import { dailyNormal, hasClimate } from "./climate";
import { fetcher, fmatAggTypeOpt, OBS } from "./conf";
import { UnitCtx } from "./Page";

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

export function useYearDaily(obs, stat, year, waterYear) {
    const [start, end] = periodBounds(year, waterYear);
    const url = "/api/var/daily/" + obs + "/" + stat + "/?include_today=1&start=" + stamp(ymd(start)) + "&end=" + stamp(ymd(end));
    const { data, error } = useSWR(url, fetcher, { refreshInterval: 300000, revalidateOnFocus: false });
    return { result: data?.result, server: data?.server, error, isLoading: !data && !error };
}

/**
 * Build the observed and normal series (DB units) for every day of the period.
 * Observed days missing from the API are null (gaps). In cumulative mode both
 * become running totals; the observed total stops after the last reported day.
 */
export function buildSeries(rows, obs, stat, year, waterYear, cumulative) {
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
        days.push({ t, obs: v ?? null, normal: normalFor(obs, stat, y, m, d) });
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

export function YearChart({ obs, stat, year, waterYear, cumulative, showNormal, today }) {
    const unit = useContext(UnitCtx);
    const fmat = OBS.get(obs).fmat;
    const { unitSymbol, precision } = unitAndPrecisionForObsType(unit, fmat);
    const conv = convFunction(unit, fmat);
    const { result, isLoading } = useYearDaily(obs, stat, year, waterYear);
    const normalOk = showNormal && hasNormal(obs, stat);
    const days = buildSeries(result, obs, stat, year, waterYear, cumulative);
    const prec = cumulative ? Math.max(precision, 0) : precision;
    const c = (v) => (v == null ? null : round(conv(v), prec));
    const isTotal = OBS.get(obs).summary === "total";
    const name = OBS.get(obs).name + (isTotal || obs === "sunpct" ? "" : " (" + fmatAggTypeOpt(stat).toLowerCase() + ")");
    const period = waterYear ? "Water year " + (year - 1) + "–" + String(year).slice(2) : String(year);
    const color = obs === "rain" ? "#2299dd" : obs === "wet" ? "#1f6fae" : obs.startsWith("sun") ? "#e6a700" : stat === "min" ? "#3377dd" : "#ff5511";
    const columns = !cumulative && isTotal;

    const plotLines = today ? [{
        value: Date.UTC(today[0], today[1] - 1, today[2]), color: "#454332", width: 1.5, dashStyle: "Dash", zIndex: 4,
        label: { text: "Today", rotation: 0, y: 14, x: 4, style: { fontSize: fontSize(12) } },
    }] : [];

    const series = [{
        type: columns ? "column" : "line",
        name: (cumulative ? "Cumulative " + name.toLowerCase() : name),
        color, lineWidth: 2, marker: { enabled: false }, zIndex: 2,
        pointPadding: 0, groupPadding: 0, borderWidth: 0,
        data: days.map((d) => [d.t, c(d.obs)]),
    }];
    if (normalOk) {
        series.push({
            type: "line", name: cumulative ? "Cumulative normal" : "Normal", color: "#555", dashStyle: cumulative ? "Solid" : "ShortDash",
            lineWidth: 1.5, marker: { enabled: false }, zIndex: 3,
            data: days.map((d) => [d.t, c(d.normal)]),
        });
    }

    const options = {
        credits: { href: null, text: "@rwcweather" },
        chart: {
            height: isMobile() ? 360 : 460, spacing: isMobile() ? [8, 2, 10, 0] : [15, 15, 15, 10],
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
        yAxis: { title: { text: OBS.get(obs).name + " / " + unitSymbol, style: { fontSize: fontSize(13) } }, min: isTotal || obs === "sunpct" ? 0 : undefined },
        tooltip: {
            shared: true, xDateFormat: "%a %e %b %Y", valueDecimals: prec, valueSuffix: " " + unitSymbol,
            formatter() {
                const pts = this.points || [];
                const o = pts.find((p) => p.series.index === 0)?.y;
                const n = pts.find((p) => p.series.index === 1)?.y;
                let s = Highcharts.dateFormat("%a %e %b %Y", this.x);
                pts.forEach((p) => { s += "<br/><span style=\"color:" + p.color + "\">●</span> " + p.series.name + ": <b>" + p.y.toFixed(prec) + " " + unitSymbol + "</b>"; });
                if (o != null && n != null) {
                    const diff = o - n;
                    s += "<br/>Anomaly: <b>" + (diff >= 0 ? "+" : "") + diff.toFixed(prec) + " " + unitSymbol + "</b>";
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
        <HighchartsReact key={[obs, stat, year, waterYear, cumulative, normalOk].join("|")} highcharts={Highcharts}
            options={options} immutable={true} />
    </Box>;
}
