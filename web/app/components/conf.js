import { FiWind } from "react-icons/fi";
import { GiDew, GiLeafSwirl } from "react-icons/gi";
import { RiHazeLine } from "react-icons/ri";
import { WiBarometer, WiDaySunny, WiHumidity, WiRain, WiThermometer, WiWindDeg } from "react-icons/wi";

export const fetcher = url => fetch(process.env.NEXT_PUBLIC_API_HOST + url).then(res => res.json());

export const OBS = new Map([
    ["temp", {
        name: "Temperature",
        summary: "avg",
        fmat: "temp",
        icon: <WiThermometer />,
    }],
    ["humi", {
        name: "Humidity",
        summary: "avg",
        fmat: "humi",
        icon: <WiHumidity />,
    }],
    ["wind", {
        name: "Wind speed",
        summary: "avg",
        fmat: "wind",
        icon: <FiWind />,
    }],
    ["rain", {
        name: "Rainfall",
        summary: "total",
        fmat: "rain",
        icon: <WiRain />,
    }],
    ["aqi", {
        name: "AQI",
        summary: "avg",
        fmat: "aqi",
        icon: <RiHazeLine />,
    }],
    ["dewpt", {
        name: "Dew Point",
        summary: "avg",
        fmat: "temp",
        icon: <GiDew />,
    }],
    ["pres", {
        name: "Air Pressure",
        summary: "avg",
        fmat: "pres",
        icon: <WiBarometer />
    }],
    ["gust", {
        name: "Gust Speed",
        summary: "avg",
        fmat: "gust",
        icon: <GiLeafSwirl />,
    }],
    ["wdir", {
        name: "Wind Direction",
        summary: "avg",
        fmat: "wdir",
        icon: <WiWindDeg />,
    }],
    // Webcam-derived; daily totals only (no minute observations)
    ["sun", {
        name: "Sunshine",
        summary: "total",
        fmat: "sun",
        icon: <WiDaySunny />,
    }],
    // Derived from "sun": each day's sunshine as % of possible (sunrise to sunset). Shown via the
    // "Show sunshine as" toggle rather than as its own variable button.
    ["sunpct", {
        name: "Sunshine (% of possible)",
        summary: "avg",
        fmat: "sunpct",
        icon: <WiDaySunny />,
        dailyStats: ["avg"],
    }],
    // Derived from rain-gauge tips (30 min either side of a spell); shown via the "Show rainfall as"
    // toggle under the Rainfall button rather than as its own variable button.
    ["wet", {
        name: "Wet hours",
        summary: "total",
        fmat: "wet",
        icon: <WiRain />,
    }],
]);

// Alternative views of one variable (the button stays the base variable).
export const SUN_VIEWS = ["sun", "sunpct"];
export const SUN_VIEW_NAMES = { sun: "Hours", sunpct: "% of possible" };
export const RAIN_VIEWS = ["rain", "wet"];
export const RAIN_VIEW_NAMES = { rain: "Amount", wet: "Wet hours" };

// Variable button -> its views and their labels (the toggle shown under the Variable buttons).
export const VIEW_GROUPS = {
    sun: { views: SUN_VIEWS, names: SUN_VIEW_NAMES, label: "Show sunshine as:" },
    rain: { views: RAIN_VIEWS, names: RAIN_VIEW_NAMES, label: "Show rainfall as:" },
};

export function baseObs(obs) {
    for (const [base, g] of Object.entries(VIEW_GROUPS)) {
        if (g.views.includes(obs)) {
            return base;
        }
    }
    return obs;
}

// Daily statistics available for a variable.
export function dailyStatsFor(obs) {
    const o = OBS.get(obs);
    if (o?.dailyStats) {
        return o.dailyStats;
    }
    return o?.summary === "total" ? ["total"] : ["min", "max", "avg"];
}

// Default daily statistic when switching to a variable: total, else the daily high, else the only one.
export function defaultDailyStat(obs, current) {
    const opts = dailyStatsFor(obs);
    if (current && opts.includes(current)) {
        return current;
    }
    return opts.includes("total") ? "total" : opts.includes("max") ? "max" : opts[0];
}

// Variables whose only daily statistic is a total (rain, sunshine).
export function isTotalObs(obs) {
    return OBS.get(obs)?.summary === "total";
}

const aggNames = {
    max: "Maximum",
    min: "Minimum",
    avg: "Average",
    total: "Total"
  }

  export function fmatAggTypeOpt(opt) {
    return aggNames[opt];
  }

  export function fmatObsOpt(obs) {
    return OBS.get(obs).name;
  }

  export function fmatYrOpt(yr) {
    return yr;
  }

  export function fmatOptCapitalize(opt) {
    return opt.substring(0, 1).toUpperCase() + opt.substring(1);
  }

  export function fmatDaysOpt(d) {
    return d + "d"
  }

  export function fmatObsOptIcon(obs) {
    return OBS.get(obs).icon;
  }
  
  export function fmatTimeOpt(t) {
    t = parseInt(t);
    if(t < 50) {
      return t + "h";
    }
    return Math.round(t / 24) + "d";
  }