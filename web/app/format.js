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
      }
    },
    pres: {
      units: {
        base: "hPa",
        us: "inHg",
      },
      conv: {
        us: p => p * 0.0002953,
      },
      precision: {
        base: 1,
        us: 2
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
      }
    },
  }

export function prettySecs(ms) {
    let s = ms / 1000;
	if(s < 100) {
		return secs + " s";
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

export function formatObs(val, obsType, signed = false, unit = true) {
  if(val == null) {
    return "-";
  }
  if (obsType == "wdir") {
    return wdirName(val);
  }
  let unitPref = UNIT;
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

export function unitForObsType(obsType) {
  const formatRules = OBS_FORMAT[obsType];
  let unitPref = UNIT;
  return (unitPref in formatRules["units"]) ? formatRules["units"][unitPref] : formatRules["units"]["base"];
}
