import { FiWind } from "react-icons/fi";
import { GiDew, GiLeafSwirl } from "react-icons/gi";
import { RiHazeLine } from "react-icons/ri";
import { WiBarometer, WiDaySunny, WiFog, WiHumidity, WiRain, WiThermometer, WiWindDeg } from "react-icons/wi";

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
        buttonName: "Wind",
        summary: "avg",
        fmat: "wind",
        icon: <FiWind />,
        dailyStats: ["max", "avg"],
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
        dailyStats: ["max", "avg"],
    }],
    ["wdir", {
        name: "Wind Direction",
        summary: "avg",
        fmat: "wdir",
        icon: <WiWindDeg />,
        dailyStats: ["avg"],
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
    // Webcam fog (LLM judge, dawn to 1 pm, 30-min frames); daily totals only. Shown via the
    // "Show sunshine as" toggle on report pages (not on the home page).
    ["fog", {
        name: "Fog hours",
        summary: "total",
        fmat: "fog",
        icon: <WiFog />,
    }],
    // 1 for any morning with recorded fog (fog hours > 0, derived from "fog" at query time); period totals are fog days.
    ["fogday", {
        name: "Fog days",
        summary: "total",
        fmat: "fogday",
        icon: <WiFog />,
    }],
    // Derived from rain-gauge tips (30 min either side of a spell); shown via the "Show rainfall as"
    // toggle under the Rainfall button rather than as its own variable button.
    ["wet", {
        name: "Wet hours",
        summary: "total",
        fmat: "wet",
        icon: <WiRain />,
    }],
    // Average rain rate when wet = rain / wet hours, derived at query time; blank on days without wet hours.
    ["wetrate", {
        name: "Rain rate (when wet)",
        summary: "avg",
        fmat: "wetrate",
        icon: <WiRain />,
        dailyStats: ["avg"],
    }],
    // Daily max rain in any 10 / 60 minutes, from gauge tips (avg_extreme type "max", with the time reached).
    ["rain10", {
        name: "Max 10-min rain",
        summary: "max",
        fmat: "rain",
        icon: <WiRain />,
        dailyStats: ["max"],
    }],
    ["rain60", {
        name: "Max 60-min rain",
        summary: "max",
        fmat: "rain",
        icon: <WiRain />,
        dailyStats: ["max"],
    }],
    // Derived at query time from the daily max and min (rwcwx/calc/derived_daily.py); one value per day, periods
    // average it. Shown via the "Show ... as" toggle under their variable's button.
    ["temprange", {
        name: "Temperature range",
        summary: "avg",
        fmat: "temprange",
        icon: <WiThermometer />,
        dailyStats: ["avg"],
    }],
    ["humirange", {
        name: "Humidity range",
        summary: "avg",
        fmat: "humirange",
        icon: <WiHumidity />,
        dailyStats: ["avg"],
    }],
    ["presrange", {
        name: "Pressure range",
        summary: "avg",
        fmat: "presrange",
        icon: <WiBarometer />,
        dailyStats: ["avg"],
    }],
    ["dewptrange", {
        name: "Dew point range",
        summary: "avg",
        fmat: "temprange",
        icon: <GiDew />,
        dailyStats: ["avg"],
    }],
    // FAO-56 reference evapotranspiration (grass), derived per day; periods add it up. Under the Temperature button.
    ["et0", {
        name: "ET0 (reference evapotranspiration)",
        shortName: "ET0",
        summary: "total",
        fmat: "et0",
        icon: <GiLeafSwirl />,
    }],
]);

// Variables derived from other daily values; they have no minute observations and no climate normals.
export const DERIVED_DAILY_OBS = ["temprange", "humirange", "presrange", "dewptrange", "et0"];

// Alternative views of one variable (the button stays the base variable).
export const SUN_VIEWS = ["sun", "sunpct"];
export const SUN_VIEW_NAMES = { sun: "Hours", sunpct: "% of possible", fog: "Fog hours", fogday: "Fog days" };
// Report pages also offer the webcam fog views under Sunshine; the home page keeps SUN_VIEWS.
export const REPORT_SUN_VIEWS = [...SUN_VIEWS, "fog", "fogday"];
export const RAIN_VIEWS = ["rain", "wet", "wetrate", "rain60", "rain10"];
export const RAIN_VIEW_NAMES = { rain: "Amount", wet: "Wet hours", wetrate: "Rate when wet", rain60: "Max 60-min", rain10: "Max 10-min" };
export const TEMP_VIEWS = ["temp", "temprange", "et0"];
export const TEMP_VIEW_NAMES = { temp: "Temperature", temprange: "Diurnal range", et0: "ET0" };
export const WIND_VIEWS = ["wind", "gust", "wdir"];
export const WIND_VIEW_NAMES = { wind: "Wind speed", gust: "Gust speed", wdir: "Wind direction" };
export const WIND_SUMMARY_VIEWS = ["wind:max", "gust:max", "wind:avg", "gust:avg", "wdir:avg"];
export const WIND_SUMMARY_NAMES = {
    "wind:max": "Max speed",
    "gust:max": "Max gust",
    "wind:avg": "Avg speed",
    "gust:avg": "Avg gust",
    "wdir:avg": "Avg direction",
};

// Variable button -> its views and their labels (the toggle shown under the Variable buttons).
export const VIEW_GROUPS = {
    sun: { views: REPORT_SUN_VIEWS, names: SUN_VIEW_NAMES, label: "Show sunshine as:" },
    rain: { views: RAIN_VIEWS, names: RAIN_VIEW_NAMES, label: "Show rainfall as:" },
    wind: { views: WIND_VIEWS, names: WIND_VIEW_NAMES, summaryViews: WIND_SUMMARY_VIEWS, summaryNames: WIND_SUMMARY_NAMES, label: "Show wind as:" },
    temp: { views: TEMP_VIEWS, names: TEMP_VIEW_NAMES, label: "Show temperature as:" },
    humi: { views: ["humi", "humirange"], names: { humi: "Humidity", humirange: "Daily range" }, label: "Show humidity as:" },
    dewpt: { views: ["dewpt", "dewptrange"], names: { dewpt: "Dew point", dewptrange: "Daily range" }, label: "Show dew point as:" },
    pres: { views: ["pres", "presrange"], names: { pres: "Pressure", presrange: "Daily range" }, label: "Show pressure as:" },
};

export function baseObs(obs) {
    for (const [base, g] of Object.entries(VIEW_GROUPS)) {
        if (g.views.includes(obs)) {
            return base;
        }
    }
    return obs;
}

export function fmatForObs(obs, stat) {
    if ((obs === "wind" || obs === "gust") && (stat === "max" || stat === "min")) {
        return "gust";
    }
    if (obs === "gust" && stat === "avg") {
        return "wind";
    }
    return OBS.get(obs).fmat;
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
    const o = OBS.get(obs);
    return o.buttonName || o.name;
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