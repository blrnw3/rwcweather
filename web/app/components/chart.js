import { Box } from "@chakra-ui/react";
import Highcharts from 'highcharts';
import HighchartsReact from 'highcharts-react-official';
import { useContext } from 'react';
import useSWR from 'swr';
import { convFunction, unitAndPrecisionForObsType } from '../format';
import { fetcher, fmatAggTypeOpt, OBS } from './conf';
import { UnitCtx } from "./Page";

let cache;

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
    const { data, error } = useSWR("/api/obs/latest?d=" + mins, fetcher, { refreshInterval: 60000 })
    if (error || !data) {
        console.log(error);
        return error ? [0, 0] : [null, 0];
    }
    let res = data["result"];
    return [res, data["server"]["offset"]];
}

function useSummary(obs, agg, period) {
    const { data, error } = useSWR("/api/var/daily/" + obs + "/" + agg + "?include_today&n=" + period, fetcher,
        { refreshInterval: 300000, revalidateOnFocus: false })
    if (error || !data) {
        console.log(error);
        return error ? [0, 0] : [null, 0];
    }
    let res = data["result"];
    return [res, data["server"]];
}

export function LatestChart(props) {
    let obs = props.obs;
    let hrs = props.hrs;

    let unit = useContext(UnitCtx);
    let obsName = OBS.get(obs).name;
    let { unitSymbol, precision } = unitAndPrecisionForObsType(unit, OBS.get(obs).fmat);
    let duration = (hrs < 50) ? hrs + " hrs" : Math.round(hrs / 24) + " days";
    let converter = convFunction(unit, OBS.get(obs).fmat);

    const [latest, offset] = useLatest(hrs * 60);

    let temp;
    let isLoading = false;
    if (!latest) {
        temp = (cache != "undefined") ? cache : [[0, 0]];
        isLoading = true;
    } else {
        cache = latest;
        temp = latest.map(x => [x["t"], converter(x[obs])]).reverse();
    }

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
            enabled: false
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
        xAxis: {
            type: "datetime"
        },
        yAxis: {
            title: {
                text: obsName + " / " + unitSymbol,
                style: {
                    fontSize: responsiveFontSize(13)
                }
            }
        },
        series: [{
            type: obs == "wdir" ? "scatter" : "line",
            data: temp,
            name: obs,
            tooltip: {
                valueDecimals: precision,
                // pointFormat: obs == "wdir" ? "{point.y} &deg;" : undefined
            },
            color: {
                linearGradient: { x1: 0, x2: 0, y1: 0, y2: 1 },
                stops: [
                    [0, "#ff5511"],
                    [1, "#ff9933"],
                ]
            },
            connectNulls: false,
        }],
    }
    return <Box mx={props.mx} my={props.my}>
        <HighchartsReact
            highcharts={Highcharts}
            options={options}
        />
    </Box>
}


export function SummaryChart(props) {
    let obs = props.obs;
    let aggType = props.aggType;
    let chartType = props.chartType;
    let aggTypePretty = fmatAggTypeOpt(aggType);

    if (obs == "rain" && aggType == "avg") {
        aggType = "total";
        aggTypePretty = "Total";
    }

    let unit = useContext(UnitCtx);
    let obsName = OBS.get(obs).name;
    let { unitSymbol, precision } = unitAndPrecisionForObsType(unit, OBS.get(obs).fmat);
    let converter = convFunction(unit, OBS.get(obs).fmat);

    const [latest, offset] = useSummary(obs, aggType, props.period);
    let data;
    let isLoading = false;
    if (!latest) {
        data = [[0, 0]];
        isLoading = true;
    }
    else {
        data = latest.map(x => [
            new Date(x["d"][0], x["d"][1] - 1, x["d"][2]).valueOf(),
            converter(x["val"])
        ]).reverse();
    }
    let options = {
        chart: {
            type: chartType,
            height: responsiveheight(props.height),
            spacing: responsiveSpacing(props.spacing),
            backgroundColor: isLoading ? "#00000022" : "#fff"
        },
        legend: {
            enabled: false
        },
        credits: {
            href: null,
            text: "@rwcweather"
        },
        title: {
            text: (isLoading ? "LOADING: " : "") + "Last " + props.period + " days " + aggTypePretty + " " + obsName + "",
            style: {
                fontSize: responsiveFontSize(18)
            }
        },
        xAxis: {
            type: "datetime"
        },
        yAxis: {
            title: {
                text: obsName + " / " + unitSymbol,
                style: {
                    fontSize: responsiveFontSize(13)
                }
            }
        },
        series: [{
            data: data,
            name: aggType + " " + obsName,
            tooltip: {
                valueDecimals: precision,
                xDateFormat: "%A, %b %e, %Y",
            },
            color: {
                linearGradient: { x1: 0, x2: 0, y1: 0, y2: 1 },
                stops: [
                    [0, "#00aa11"],
                    [1, "#33dd44"],
                ]
            },
            connectNulls: false,
        }],
        plotOptions: {
            column: {
                groupPadding: 0,
                pointPadding: 0,
                threshold: null
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
