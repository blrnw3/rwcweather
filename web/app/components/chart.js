import { Box } from "@chakra-ui/react";
import Highcharts from 'highcharts';
import HighchartsReact from 'highcharts-react-official';
import { useContext } from 'react';
import useSWR from 'swr';
import { convFunction, unitAndPrecisionForObsType } from '../format';
import { daysInMonth } from './dateUtil';
import { DERIVED_PARENT, fetcher, fmatAggTypeOpt, fmatForObs, OBS } from './conf';
import { LIVE_SWR, useLivePoll } from './liveRefresh';
import { UnitCtx } from "./Page";

let cache;

// Y-axis scaling per variable. The axis always autoscales to the data; the lists below only decide
// what happens at zero.
//
// IMPORTANT: "auto" must be expressed as null, never undefined. HighchartsReact updates the existing
// chart in place (chart.update), and Highcharts' option merge skips undefined values, so `min: undefined`
// leaves the previous variable's `min: 0` in force. That is what pinned temperature/pressure to a
// zero-based axis after clicking through rain or sunshine (#83).
//
// Amounts and percentages of time: bars/areas measure "how much", so they start at a true 0 baseline.
const ZERO_BASELINE = ["rain", "wet", "wetrate", "rain10", "rain60", "sun", "sunpct", "fog", "fogday", "solr", "et0"];
// Can't go negative but are levels, not amounts: autoscale to the data, just never below 0.
const ZERO_FLOOR = ["wind", "gust", "aqi", "humi", "temprange", "humirange", "presrange", "dewptrange"];

// Percentages that cannot exceed 100: the axis may autoscale below that, but tick rounding must never take it past
// 100% (humidity near saturation used to get a 0-120 axis).
const PCT_CEILING = ["humi", "sunpct", "humirange"];

export function yAxisScale(obs, values) {
    const ceiling = PCT_CEILING.includes(obs) ? 100 : null;
    if (ZERO_BASELINE.includes(obs)) {
        // An all-zero series (a dry spell, a sunless day) would otherwise get a -0.5..0.5 axis; keep it on the baseline.
        const allZero = !values.some((v) => Number.isFinite(v) && v !== 0);
        return { min: 0, max: allZero ? 1 : null, floor: null, ceiling };
    }
    return { min: null, max: null, floor: ZERO_FLOOR.includes(obs) ? 0 : null, ceiling };
}

function responsiveFontSize(base) {
    let scale = 1;
    if (typeof window !== "undefined") {
        let w = window.innerWidth;
        if (w < 360) {
            scale = 0.6;
        } else if (w < 768) {
            scale = 0.75
        } else if (w < 1280) {
            scale = 0.9
        }
    }
    return Math.round(base * scale).toString() + "px";
}

function responsiveSpacing(spacing) {
    if (typeof window !== "undefined") {
        let w = window.innerWidth;
        if (w < 768 && spacing[0] > 10) {
            return [2, 2, 10, 0];
        }
    }
    return spacing;
}

function responsiveheight(hgt) {
    if (typeof window !== "undefined") {
        let w = window.innerWidth;
        if (hgt === "responsive") {
            return w < 768 ? "65%" : "44%";
        }
    }
    return hgt;
}

function useLatest(mins) {
    const key = "/api/obs/latest?d=" + mins;
    const { data, error, revalidate } = useSWR(key, fetcher, LIVE_SWR);
    useLivePoll(key, revalidate, 60000, { minAgeMs: 10000 });
    if (error || !data) {
        console.log(error);
        return error ? [0, 0] : [null, 0];
    }
    let res = data["result"];
    return [res, data["server"]["offset"]];
}

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function summaryQuery(period, year, month) {
    if (year && year !== "recent") {
        const y = Number(year);
        if (month && month !== "all") {
            const m = Number(month);
            const mm = String(m).padStart(2, "0");
            const lastDay = String(daysInMonth(y, m)).padStart(2, "0");
            return "?start=" + y + mm + "01&end=" + y + mm + lastDay;
        }
        return "?start=" + y + "0101&end=" + y + "1231";
    }
    return "?include_today&n=" + period;
}

function useSummary(obs, agg, period, year, month) {
    const query = summaryQuery(period, year, month);
    // obs null: no request (lets a chart call this hook unconditionally for an optional second series).
    const { data, error } = useSWR(obs ? "/api/var/daily/" + obs + "/" + agg + query : null, fetcher,
        { refreshInterval: 300000, revalidateOnFocus: false })
    if (error || !data) {
        console.log(error);
        return error ? [0, 0] : [null, 0];
    }
    let res = data["result"];
    return [res, data["server"]];
}

// Wind is shown as speed and gust together: speed in the chart's own colour, gust in a lighter blue
// drawn behind it (gust >= speed, so the speed line stays on top).
export const GUST_COLOR = "#4f8fd6";
export const GUST_FILL = "#a9c9ef";
const LATEST_COLOR = {
    linearGradient: { x1: 0, x2: 0, y1: 0, y2: 1 },
    stops: [[0, "#ff5511"], [1, "#ff9933"]],
};

export function LatestChart(props) {
    let obs = props.obs;
    let hrs = props.hrs;
    // "wind" plots speed + gust as two series; gust/wdir on their own are single series.
    const withGust = obs === "wind";

    let unit = useContext(UnitCtx);
    let obsName = withGust ? "Wind speed & gust" : OBS.get(obs).name;
    let { unitSymbol, precision } = unitAndPrecisionForObsType(unit, OBS.get(obs).fmat);
    let gustPrecision = unitAndPrecisionForObsType(unit, OBS.get("gust").fmat).precision;
    let duration = (hrs < 50) ? hrs + " hrs" : Math.round(hrs / 24) + " days";
    let converter = convFunction(unit, OBS.get(obs).fmat);
    let gustConverter = convFunction(unit, OBS.get("gust").fmat);

    const [latest, offset] = useLatest(hrs * 60);

    let temp;
    let gust = [];
    let isLoading = false;
    if (!latest) {
        // While a new range loads, keep showing the last points for this variable (cache holds [t, value] pairs).
        temp = cache && cache.obs === obs ? cache.points : [];
        gust = cache && cache.obs === obs ? cache.gust : [];
        isLoading = true;
    } else {
        temp = latest.map(x => [x["t"], converter(x[obs])]).reverse();
        gust = withGust ? latest.map(x => [x["t"], gustConverter(x["gust"])]).reverse() : [];
        cache = { obs, points: temp, gust };
    }

    const series = withGust ? [{
        id: "gust",
        type: "line",
        data: gust,
        name: "Gust",
        color: GUST_COLOR,
        lineWidth: 1,
        zIndex: 1,
        tooltip: { valueDecimals: gustPrecision, valueSuffix: " " + unitSymbol },
        connectNulls: false,
    }, {
        id: "wind",
        type: "line",
        data: temp,
        name: "Speed",
        color: LATEST_COLOR,
        lineWidth: 2,
        zIndex: 2,
        tooltip: { valueDecimals: precision, valueSuffix: " " + unitSymbol },
        connectNulls: false,
    }] : [{
        id: "main",
        type: obs == "wdir" ? "scatter" : "line",
        data: temp,
        name: obs,
        tooltip: {
            valueDecimals: precision,
        },
        color: LATEST_COLOR,
        connectNulls: false,
    }];

    let options = {
        chart: {
            height: responsiveheight(props.height),
            spacing: responsiveSpacing(props.spacing),
            backgroundColor: isLoading ? "#00000022" : "#fff"
        },
        events: {
            load() {
                this.showLoading();
            }
        },
        legend: {
            enabled: withGust,
            align: "right",
            verticalAlign: "top",
            floating: true,
            y: 20,
            itemStyle: { fontSize: responsiveFontSize(12) },
        },
        credits: {
            href: null,
            text: "@rwcweather"
        },
        title: {
            text: (isLoading ? "LOADING: " : "") + "Last " + duration + " " + obsName,
            style: {
                fontSize: responsiveFontSize(18)
            }
        },
        time: {
            timezoneOffset: -60 * offset
        },
        tooltip: {
            shared: withGust,
        },
        xAxis: {
            type: "datetime"
        },
        yAxis: {
            ...yAxisScale(obs, temp.concat(gust).map(([, v]) => v)),
            title: {
                text: (withGust ? "Wind" : obsName) + " / " + unitSymbol,
                style: {
                    fontSize: responsiveFontSize(13)
                }
            }
        },
        series,
    }
    // oneToOne: series dropped from the options (gust, when leaving wind) are removed from the chart.
    return <Box mx={props.mx} my={props.my}>
        <HighchartsReact
            highcharts={Highcharts}
            options={options}
            oneToOne={true}
        />
    </Box>
}


export function SummaryChart(props) {
    let obs = props.obs;
    let aggType = props.aggType;
    let chartType = props.chartType;
    let aggTypePretty = fmatAggTypeOpt(aggType);

    if (OBS.get(obs).summary == "total" && aggType != "total") {
        aggType = "total";
        aggTypePretty = "Total";
    }

    let unit = useContext(UnitCtx);
    let obsName = OBS.get(obs).name;
    let fmat = fmatForObs(obs, aggType);
    let { unitSymbol, precision } = unitAndPrecisionForObsType(unit, fmat);
    let converter = convFunction(unit, fmat);
    // Home 30-day chart: wind speed and gust (same statistic) together; gust drawn behind in light blue.
    const withGust = Boolean(props.withGust) && obs === "wind";
    const gustFmat = fmatForObs("gust", aggType);
    const gustPrecision = unitAndPrecisionForObsType(unit, gustFmat).precision;
    const gustConverter = convFunction(unit, gustFmat);
    if (withGust) {
        obsName = "Wind speed & gust";
    }

    const [latest, offset] = useSummary(obs, aggType, props.period, props.year, props.month);
    const [latestGust] = useSummary(withGust ? "gust" : null, aggType, props.period, props.year, props.month);
    const toPoints = (rows, conv) => rows.map(x => [
        new Date(x["d"][0], x["d"][1] - 1, x["d"][2]).valueOf(),
        conv(x["val"])
    ]).reverse();
    const gustData = withGust && latestGust ? toPoints(latestGust, gustConverter) : [];
    let data;
    let isLoading = false;
    if (!latest) {
        data = [];
        isLoading = true;
    }
    else {
        data = toPoints(latest, converter);
    }
    if (withGust && !latestGust) {
        isLoading = true;
    }
    const mainColor = {
        linearGradient: { x1: 0, x2: 0, y1: 0, y2: 1 },
        stops: [
            [0, "#00aa11"],
            [1, "#33dd44"],
        ]
    };
    const series = withGust ? [{
        id: "gust",
        data: gustData,
        name: aggTypePretty + " gust",
        color: GUST_FILL,
        borderColor: GUST_COLOR,
        zIndex: 1,
        tooltip: { valueDecimals: gustPrecision, valueSuffix: " " + unitSymbol, xDateFormat: "%A, %b %e, %Y" },
        connectNulls: false,
    }, {
        id: "wind",
        data: data,
        name: aggTypePretty + " speed",
        color: mainColor,
        zIndex: 2,
        tooltip: { valueDecimals: precision, valueSuffix: " " + unitSymbol, xDateFormat: "%A, %b %e, %Y" },
        connectNulls: false,
    }] : [{
        id: "main",
        data: data,
        name: aggType + " " + obsName,
        tooltip: {
            valueDecimals: precision,
            xDateFormat: "%A, %b %e, %Y",
        },
        color: mainColor,
        connectNulls: false,
    }];
    const periodTitle = (props.year && props.year !== "recent")
        ? ((props.month && props.month !== "all" ? MONTH_NAMES[Number(props.month) - 1] + " " : "") + props.year)
        : ("Last " + props.period + " days");
    let options = {
        chart: {
            type: chartType,
            height: responsiveheight(props.height),
            spacing: responsiveSpacing(props.spacing),
            backgroundColor: isLoading ? "#00000022" : "#fff"
        },
        legend: {
            enabled: withGust,
            align: "right",
            verticalAlign: "top",
            floating: true,
            y: 20,
            itemStyle: { fontSize: responsiveFontSize(12) },
        },
        tooltip: {
            shared: withGust,
        },
        credits: {
            href: null,
            text: "@rwcweather"
        },
        title: {
            text: (isLoading ? "LOADING: " : "") + periodTitle + " " + (DERIVED_PARENT[obs] ? "" : aggTypePretty + " ") + obsName
                + (!isLoading && !data.some(([, v]) => Number.isFinite(v)) ? " – no data in this period" : ""),
            style: {
                fontSize: responsiveFontSize(18)
            }
        },
        xAxis: {
            type: "datetime"
        },
        yAxis: {
            ...yAxisScale(obs, data.concat(gustData).map(([, v]) => v)),
            title: {
                text: (withGust ? "Wind" : obsName) + " / " + unitSymbol,
                style: {
                    fontSize: responsiveFontSize(13)
                }
            }
        },
        series,
        plotOptions: {
            column: {
                groupPadding: 0,
                pointPadding: 0,
                threshold: null,
                // Speed and gust share each day's slot, gust behind speed.
                grouping: !withGust,
            },
            line: {
                connectNulls: false,
            }
        }
    }
    return <Box mx={props.mx} my={props.my}>
        <HighchartsReact
            highcharts={Highcharts}
            options={options}
            oneToOne={true}
        />
    </Box>
}


function stationWallTime(localTimestamp) {
    const match = localTimestamp?.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/);
    if (!match) {
        return null;
    }
    return Date.UTC(
        Number(match[1]), Number(match[2]) - 1, Number(match[3]),
        Number(match[4]), Number(match[5]), Number(match[6])
    );
}

export function DailyChart({ observations, obs, dateLabel, isLoading, ...boxProps }) {
    const unit = useContext(UnitCtx);
    const obsObj = OBS.get(obs);
    const { unitSymbol, precision } = unitAndPrecisionForObsType(unit, obsObj.fmat);
    const converter = convFunction(unit, obsObj.fmat);
    const data = (observations || [])
        .filter((reading) => reading[obs] != null)
        .map((reading) => [stationWallTime(reading.t_local), converter(reading[obs])])
        .filter(([timestamp]) => timestamp != null);
    const hasData = data.length > 0;

    const options = {
        chart: {
            height: responsiveheight("responsive"),
            spacing: responsiveSpacing([20, 20, 25, 10]),
            backgroundColor: isLoading ? "#00000022" : "#fff",
        },
        legend: { enabled: false },
        credits: { href: null, text: "@rwcweather" },
        title: {
            text: isLoading
                ? "Loading daily chart…"
                : (hasData ? obsObj.name + " on " + dateLabel : "No " + obsObj.name.toLowerCase() + " observations"),
            style: { fontSize: responsiveFontSize(18) },
        },
        time: { timezoneOffset: 0 },
        xAxis: {
            type: "datetime",
            title: { text: "Local time" },
        },
        yAxis: {
            ...yAxisScale(obs, data.map(([, v]) => v)),
            title: {
                text: obsObj.name + " / " + unitSymbol,
                style: { fontSize: responsiveFontSize(13) },
            },
        },
        series: [{
            type: obs === "wdir" ? "scatter" : "line",
            data,
            name: obsObj.name,
            tooltip: {
                valueDecimals: precision,
                xDateFormat: "%H:%M",
            },
            color: {
                linearGradient: { x1: 0, x2: 0, y1: 0, y2: 1 },
                stops: [[0, "#ff5511"], [1, "#ff9933"]],
            },
            connectNulls: false,
        }],
    };

    return <Box {...boxProps}>
        <HighchartsReact highcharts={Highcharts} options={options} />
    </Box>;
}
