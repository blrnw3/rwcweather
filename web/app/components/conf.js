import { FiWind } from "react-icons/fi";
import { GiDew, GiLeafSwirl } from "react-icons/gi";
import { RiHazeLine } from "react-icons/ri";
import { WiBarometer, WiHumidity, WiRain, WiThermometer, WiWindDeg } from "react-icons/wi";

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
]);

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