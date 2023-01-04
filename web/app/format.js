const UNIT = "uk";  // TODO

const OBS_FORMAT = {
    temp: {
      units: {
        base: String.fromCharCode(176) + "C",
        us: String.fromCharCode(176) + "F",
      },
      conv: {
        us: c => c * 9/5 + 32
      },
      precision: {
        base: 1
      },
      scale: {
        base: [0, 5, 10, 15, 20, 25, 30, 35],
        us: [32, 40, 50, 60, 70, 80, 90, 100]
      }
    },
    abs_temp: {
      units: {
        base: String.fromCharCode(176) + "C",
        us: String.fromCharCode(176) + "F",
      },
      conv: {
        us: c => c * 9/5
      },
      precision: {
        base: 1
      }
    },
    wind: {
      units: {
        base: "mph",
        eu: "kph",
      },
      conv: {
        eu: w => w * 1.60934
      },
      precision: {
        base: 1
      },
      scale: {
        base: [1, 2, 3, 5, 10, 15, 20, 25],
        eu: [1, 2, 3, 5, 10, 20, 30, 40]
      }
    },
    gust: {
      units: {
        base: "mph",
        eu: "kph",
      },
      conv: {
        eu: w => w * 1.60934
      },
      precision: {
        base: 0
      },
      scale: {
        base: [1, 2, 3, 5, 10, 15, 20, 25],
        eu: [1, 2, 3, 5, 10, 20, 30, 40]
      }
    },
    humi: {
      units: {
        base: "%",
      },
      conv: {
      },
      precision: {
        base: 0
      },
      scale: {
        base: [10, 20, 30, 40, 50, 60, 70, 80, 90],
      }
    },
    rain: {
      units: {
        base: "mm",
        us: "in",
      },
      conv: {
        uk: r => r * 25.4,
        eu: r => r * 25.4,
      },
      precision: {
        base: 1,
        us: 2
      },
      scale: {
        base: [0.2, 1, 3, 5, 10, 15, 25, 50],
        us: [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1, 2]
      }
    },
    pres: {
      units: {
        base: "mb",
        us: "in",
      },
      conv: {
        us: p => p * 0.02953,
      },
      precision: {
        base: 1,
        us: 2
      },
      scale: {
        base: [1000, 1005, 1010, 1015, 1020, 1025, 1030, 1035],
        us: [29.5, 29.6, 29.7, 29.8, 29.9, 30, 30.1, 30.2, 30.3]
      }
    },
    aqi: {
      units: {
        base: "",
      },
      conv: {
      },
      precision: {
        base: 0,
      },
      scale: {
        base: [10, 25, 50, 75, 100, 150, 200, 300, 500],
      }
    },
    pm2: {
      units: {
        base: "PPM",
      },
      conv: {
      },
      precision: {
        base: 0,
      }
    },
    wdir: {
      units: {
        base: String.fromCharCode(176),
      },
      conv: {
      },
      precision: {
        base: 0,
      },
      scale: {
        base: [45, 90, 135, 180, 225, 270, 315, 360],
      }
    },
  }

export function prettySecs(ms) {
    let s = ms / 1000;
	if(s < 100) {
		return s + " s";
    }
    let ago;
	if(s < 7200) {
		ago = Math.round(s / 60) + " mins";
	} else if(s < (3600 * 48.5)) {
		ago = Math.round(s / 3600) + " hours";
	} else {
		ago = Math.round(s / 86400) + " days";
	}
	return ago;
}

export function timeOf(dt) {
  if(dt == null) {
    return "-";
  }
  const dt_fmat = new Intl.DateTimeFormat("en-GB", {hour: "2-digit", minute: "2-digit"});
  return dt_fmat.format(new Date(dt));
}

export function wdirName(degs) {
  let labels = ["N","NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW","SW", "WSW", "W", "WNW", "NW", "NNW","N"];
	return labels[ Math.round(degs / 22.5) ];
}

export function aqiStatus(aqi) {
  if(aqi < 50) {
    return ["🟢", "Healthy"];
  }
  if(aqi < 100) {
    return ["🟡", "Moderate"];
  }
  if(aqi < 150) {
    return ["​🟠​", "Poor"];
  }
  if(aqi < 200) {
    return ["🔴", "Unhealthy"];
  }
  if(aqi < 300) {
    return ["🟣", "Very unhealthy"];
  }
  return ["⚫", "Hazardous"];
}

export function moonPhase(phaseFraction) {
  let names = [
    ["New Moon", "🌑"],
    ["Waxing Crescent", "🌒"],
    ["First Quarter", "🌓"],
    ["Waxing Gibbous", "🌔"],
    ["Full Moon", "🌕"],
    ["Waning Gibbous", "🌖"],
    ["Third Quarter", "🌗"],
    ["Waning Crescent", "🌘"],
    ["New Moon", "🌑"],
  ];
  return names[ Math.round(phaseFraction * 8) ];
}

export function formatObs(unitPref, val, obsType, signed = false, unit = true) {
  if(val == null) {
    return "-";
  }
  if (obsType == "wdir") {
    return wdirName(val);
  }
  const formatRules = OBS_FORMAT[obsType];
  if (formatRules == null) {
    throw "Invalid obsType for conversion: " + obsType;
  }
  if (unitPref in formatRules["conv"]) {
    val = formatRules["conv"][unitPref](val);
  }
  let precision = (unitPref in formatRules["precision"]) ? formatRules["precision"][unitPref] : formatRules["precision"]["base"];
  let unitStr = (unitPref in formatRules["units"]) ? formatRules["units"][unitPref] : formatRules["units"]["base"];
  let signStr = (signed && val >= 0) ? "+" : "";
  let finalUnitStr = unit ? (" " + unitStr) : "";

  return signStr + val.toFixed(precision).toString() + finalUnitStr;
}

export function convFunction(unitPref, obsType) {
  const formatRules = OBS_FORMAT[obsType];
  if (unitPref in formatRules["conv"]) {
    return formatRules["conv"][unitPref];
  }
  return (x) => x;
}

export function unitForObsType(unitPref, obsType) {
  const formatRules = OBS_FORMAT[obsType];
  return (unitPref in formatRules["units"]) ? formatRules["units"][unitPref] : formatRules["units"]["base"];
}

export function scaleForObsType(unitPref, obsType) {
  const formatRules = OBS_FORMAT[obsType];
  return (unitPref in formatRules["scale"]) ? formatRules["scale"][unitPref] : formatRules["scale"]["base"];
}

export function unitAndPrecisionForObsType(unitPref, obsType) {
  const formatRules = OBS_FORMAT[obsType];
  let unitSymbol = (unitPref in formatRules["units"]) ? formatRules["units"][unitPref] : formatRules["units"]["base"];
  let precision = (unitPref in formatRules["precision"]) ? formatRules["precision"][unitPref] : formatRules["precision"]["base"];
  return { unitSymbol, precision };
}
