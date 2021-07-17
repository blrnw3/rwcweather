export const fetcher = url => fetch(process.env.NEXT_PUBLIC_API_HOST + url).then(res => res.json());

export const OBS = new Map([
    ["temp", {
        name: "Temperature",
        summary: "avg",
        fmat: "temp",
    }],
    ["humi", {
        name: "Humidity",
        summary: "avg",
        fmat: "humi",
    }],
    ["wind", {
        name: "Wind speed",
        summary: "avg",
        fmat: "wind",
    }],
    ["rain", {
        name: "Rainfall",
        summary: "total",
        fmat: "rain",
    }],
    ["aqi", {
        name: "AQI",
        summary: "avg",
        fmat: "aqi",
    }],
    ["dewpt", {
        name: "Dew Point",
        summary: "avg",
        fmat: "temp",
    }],
    ["pres", {
        name: "Air Pressure",
        summary: "avg",
        fmat: "pres",
    }],
    ["gust", {
        name: "Gust Speed",
        summary: "avg",
        fmat: "gust",
    }],
    ["wdir", {
        name: "Wind Direction",
        summary: "avg",
        fmat: "wdir",
    }],
]);