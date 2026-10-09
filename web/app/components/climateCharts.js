import { Box } from "@chakra-ui/react";
import Highcharts from "highcharts";
import HighchartsMore from "highcharts/highcharts-more";
import HighchartsReact from "highcharts-react-official";
import { useContext } from "react";
import { convFunction, unitAndPrecisionForObsType } from "../format";
import { dailyNormalsForYear, hasClimate, monthlyNormals } from "./climate";
import { UnitCtx } from "./Page";

// Charts of the climate normals for /reports/climate. All values come from
// data/climate.js via the climate module (DB units: degC, inches) and are
// converted to the visitor's units here. Rendered client-side only (the page
// mounts them after hydration, as the unit preference lives in localStorage).

// columnrange / arearange live in highcharts-more; it touches `window`, so
// only initialise it in the browser.
if (typeof Highcharts === "object" && typeof window !== "undefined" && !Highcharts.seriesTypes.columnrange) {
    HighchartsMore(Highcharts);
}

const MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const TEMP_LOW = "#3377dd";
const TEMP_HIGH = "#ff5511";
const TEMP_MEAN = "#ff9933";
const RAIN = "#2299dd";

function isMobile() {
    return typeof window !== "undefined" && window.innerWidth < 768;
}

function fontSize(base) {
    return Math.round(base * (isMobile() ? 0.75 : 1)) + "px";
}

const COMMON = () => ({
    credits: { href: null, text: "@rwcweather" },
    chart: {
        height: isMobile() ? 360 : 420,
        spacing: isMobile() ? [8, 2, 10, 0] : [15, 15, 15, 10],
        backgroundColor: "#fff",
    },
    legend: { itemStyle: { fontSize: fontSize(12) } },
});

function round(value, precision) {
    return value == null ? null : Number(value.toFixed(precision));
}

function tempScale(unit) {
    const { unitSymbol, precision } = unitAndPrecisionForObsType(unit, "temp");
    return { conv: convFunction(unit, "temp"), unitSymbol, precision };
}

/** Monthly normals: low-high temperature range columns plus rain columns (2nd axis). */
export function MonthlyNormalsChart({ period }) {
    const unit = useContext(UnitCtx);
    const temp = tempScale(unit);
    const rainFmt = unitAndPrecisionForObsType(unit, "rain");
    const rainConv = convFunction(unit, "rain");
    const lows = monthlyNormals("temp", "min");
    const highs = monthlyNormals("temp", "max");
    const rain = monthlyNormals("rain", "total");
    const hasTemp = lows != null && highs != null;

    const series = [];
    if (rain) {
        series.push({
            type: "column", name: "Rainfall", yAxis: 1, color: RAIN, opacity: 0.55,
            data: rain.map((v) => round(rainConv(v), rainFmt.precision)),
            tooltip: { valueSuffix: " " + rainFmt.unitSymbol, valueDecimals: rainFmt.precision },
            pointPadding: 0.05, groupPadding: 0.1, zIndex: 1,
        });
    }
    if (hasTemp) {
        series.push({
            type: "columnrange", name: "Temperature low – high", yAxis: 0, zIndex: 2,
            data: lows.map((lo, m) => [round(temp.conv(lo), temp.precision), round(temp.conv(highs[m]), temp.precision)]),
            color: {
                linearGradient: { x1: 0, x2: 0, y1: 0, y2: 1 },
                stops: [[0, TEMP_HIGH], [1, TEMP_LOW]],
            },
            borderRadius: 3, pointWidth: isMobile() ? 9 : 16,
            tooltip: { valueSuffix: " " + temp.unitSymbol, valueDecimals: temp.precision },
        });
        series.push({
            type: "line", name: "Temperature mean", yAxis: 0, zIndex: 3, color: TEMP_MEAN,
            marker: { symbol: "circle", radius: 3 },
            data: (monthlyNormals("temp", "avg") || []).map((v) => round(temp.conv(v), temp.precision)),
            tooltip: { valueSuffix: " " + temp.unitSymbol, valueDecimals: temp.precision },
        });
    }
    const base = COMMON();
    const options = {
        ...base,
        title: { text: "Monthly normals" + (period ? ", " + period : ""), style: { fontSize: fontSize(18) } },
        xAxis: { categories: MONTH_SHORT, crosshair: true },
        yAxis: [
            {
                title: { text: "Temperature / " + temp.unitSymbol, style: { fontSize: fontSize(13), color: TEMP_HIGH } },
                labels: { style: { color: TEMP_HIGH } },
                visible: hasTemp,
            },
            {
                title: { text: "Rainfall / " + rainFmt.unitSymbol, style: { fontSize: fontSize(13), color: RAIN } },
                labels: { style: { color: RAIN } },
                opposite: true, min: 0, visible: rain != null,
            },
        ],
        tooltip: { shared: true },
        series,
    };
    return <Box id="climate-monthly-chart" mt="4">
        <HighchartsReact highcharts={Highcharts} options={options} />
    </Box>;
}

/** Daily temperature normals (interpolated) for every day of the current year. */
export function DailyTempNormalsChart({ year, today }) {
    const unit = useContext(UnitCtx);
    if (!hasClimate("temp", "min") || !hasClimate("temp", "max")) {
        return null;
    }
    const temp = tempScale(unit);
    const ts = ({ month, day }) => Date.UTC(year, month - 1, day);
    const conv = (v) => round(temp.conv(v), temp.precision);
    const lows = dailyNormalsForYear("temp", "min", year);
    const highs = dailyNormalsForYear("temp", "max", year);
    const means = dailyNormalsForYear("temp", "avg", year);
    const line = (name, days, color, width) => ({
        type: "line", name, color, lineWidth: width, marker: { enabled: false }, zIndex: 2,
        data: days.map((d) => [ts(d), conv(d.value)]),
    });
    const plotLines = today ? [{
        value: Date.UTC(today[0], today[1] - 1, today[2]), color: "#454332", width: 1.5, dashStyle: "Dash", zIndex: 4,
        label: { text: "Today", rotation: 0, y: 14, x: 4, style: { fontSize: fontSize(12) } },
    }] : [];

    const base = COMMON();
    const options = {
        ...base,
        title: { text: "Daily temperature normals", style: { fontSize: fontSize(18) } },
        time: { useUTC: true },
        xAxis: { type: "datetime", dateTimeLabelFormats: { month: "%b", year: "%b" }, plotLines, crosshair: true },
        yAxis: { title: { text: "Temperature / " + temp.unitSymbol, style: { fontSize: fontSize(13) } } },
        tooltip: {
            shared: true, xDateFormat: "%e %B", valueSuffix: " " + temp.unitSymbol, valueDecimals: temp.precision,
        },
        series: [
            {
                type: "arearange", name: "Low – high range", color: TEMP_MEAN, fillOpacity: 0.15, lineWidth: 0,
                enableMouseTracking: false, showInLegend: false, zIndex: 0,
                data: lows.map((d, i) => [ts(d), conv(d.value), conv(highs[i].value)]),
            },
            line("Normal high", highs, TEMP_HIGH, 2),
            line("Normal mean", means, TEMP_MEAN, 1.5),
            line("Normal low", lows, TEMP_LOW, 2),
        ],
    };
    return <Box id="climate-daily-chart" mt="4">
        <HighchartsReact highcharts={Highcharts} options={options} />
    </Box>;
}
