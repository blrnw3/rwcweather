from datetime import datetime
from dateutil import tz

from rwcwx.config import TZ


class CumulusObs:

    # TODO: confify
    DATE_TIME_FORMAT = "%d/%m/%y %H:%M:%S"

    def __init__(self, path: str) -> None:
        self.path = path
        with open(path) as f:
            raw_line = f.read()
        obs_raw = raw_line.split(" ")

        if len(obs_raw) < 50:
            raise ValueError(f"Path invalid or partial. Only {len(obs_raw)} fields")

        self.dt_local = datetime.strptime(
            f"{obs_raw[0]} {obs_raw[1]}", self.DATE_TIME_FORMAT
        ).replace(
            tzinfo=TZ
        )
        self.dt = self.dt_local.astimezone(tz.UTC)
        self.dt_minute = self.dt.replace(second=0)

        self.temp = obs_raw[2]
        self.humi = int(obs_raw[3])
        self.dewp = obs_raw[4]
        self.wind = obs_raw[5]
        self.gust = obs_raw[6]
        self.wdir = int(obs_raw[7])
        self.rate = obs_raw[8]
        self.rain = float(obs_raw[9])
        self.pres = obs_raw[10]

        self.intemp = obs_raw[22]
        self.inhumi = obs_raw[23]

        self.daylight = (obs_raw[49] == "1")
        self.solr_max = obs_raw[56]
        self.feels = obs_raw[58]

        self.wet = float(obs_raw[47]) > 0

    def as_obs_table_params(self) -> dict:
        return dict(
            t=self.dt_minute,
            t_obs=self.dt,
            temp=self.temp,
            humi=self.humi,
            wind=self.wind,
            gust=self.gust,
            wdir=self.wdir,
            rain=self.rain,
            pres=self.pres,
            intemp=self.intemp,
            inhumi=self.inhumi,
            wet=self.wet
        )
