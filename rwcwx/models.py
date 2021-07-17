import math
import os

import aqi
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Date, Enum, Integer, String, Numeric, DateTime, Float, Time, Boolean

from rwcwx.config import TZ
from rwcwx.model.db import Db
from rwcwx.model.wx import Model

mysql_url = os.getenv("MYSQL_URL", "root:test@127.0.0.1:3307/wx")
db = Db(f"mysql://{mysql_url}", echo_pool=True, pool_recycle=3600)
# For non-ORM inserts. For ORM-queries, use the models below
m = Model(db)


Base = declarative_base()


class Obs(Base):
    __tablename__ = "obs"

    t = Column(DateTime, primary_key=True)
    src = Column()
    temp = Column()
    humi = Column()
    rain = Column()
    pres = Column()
    wind = Column()
    gust = Column()
    wdir = Column()
    # solr = Column()
    pm2 = Column()
    # wet = Column()
    # sun = Column()
    inhumi = Column()
    intemp = Column()
    t_obs = Column()
    t_mod = Column()

    @property
    def dewpt(self) -> float:
        t = float(self.temp)
        gamma = (17.271 * t) / (237.7 + t) + math.log(self.humi / 100)
        return (237.7 * gamma) / (17.271 - gamma)

    @property
    def feels(self) -> float:
        """ Wind chill when temp is sub 10, heat index when dew point is above 10, else just the temp """
        t = float(self.temp)
        w = float(self.wind)
        feel = t
        if t < 10 and w > 3:
            # http://en.wikipedia.org/wiki/Wind_chill#North_American_and_UK_wind_chill_index
            x = pow(w * 1.61, 0.16)
            feel = 13.12 + t * (0.6215 + 0.3965 * x) - 11.37 * x
        elif t > 26:  # Heat index formula is not valid below this
            # humidex = t + 0.5555 * (6.11 * pow(math.e, 5417.753 * (0.003660858 - 1 / (d+273.15))) - 10)
            r = float(self.humi)
            t2 = pow(t, 2)
            r2 = pow(r, 2)
            feel = (C[0] + C[1] * t + C[2] * r + C[3] * t * r +
                    C[4] * t2 + C[5] * r2 + C[6] * t2 * r +
                    C[7] * t * r2 + C[8] * t2 * r2)
        return feel

    @property
    def aqi(self) -> int:
        return int(aqi.to_aqi([(aqi.POLLUTANT_PM25, float(self.pm2))]))

    @property
    def dict_(self) -> dict:
        d = self.__dict__
        d.pop("_sa_instance_state", None)
        d.pop("t_mod", None)
        d["dewpt"] = round(self.dewpt, 1)
        d["feels"] = round(self.feels, 1)
        d["aqi"] = self.aqi
        d["t_local"] = self.t.astimezone(TZ).isoformat()
        return d

    def __repr__(self):
        return f"<Obs:{self.t}>"


class AvgExt(Base):
    __tablename__ = "avg_extreme"

    d = Column(Date, primary_key=True)
    var = Column(Enum('rain', 'temp', 'humi', 'pres', 'wind', 'gust', 'wdir', 'solr', 'wet', 'sun', 'feels', 'inhumi',
                      'intemp', 'night_temp', 'day_temp', 'day_wet', 'rate', 'frost', 'pm2', 'dewpt', 'aqi'),
                 primary_key=True)
    type = Column(Enum('avg', 'total', 'min', 'max'), primary_key=True)
    period = Column(Enum("day"), primary_key=True)
    val = Column(Float)
    # val_exact = Column(Numeric)
    at = Column(DateTime)
    cnt = Column(Integer)
    t_mod = Column(DateTime)
    overridden = Column(Boolean)
    comment = Column(String(length=255))

    @property
    def dict_(self) -> dict:
        d_ = self.__dict__.copy()
        d_.pop("_sa_instance_state", None)
        d_.pop("t_mod", None)
        d_["d"] = (self.d.year, self.d.month, self.d.day)
        if self.at is not None:
            at_local = self.at.astimezone(TZ)
            d_["at_hm"] = (at_local.hour, at_local.minute)
        return d_

    @property
    def simple_dict_(self) -> dict:
        return {k: v for k, v in self.dict_.items() if k in ("d", "at", "val", "at_hm")}

    def __repr__(self):
        return f"<AvgExt:{self.d}-{self.var}-{self.type}-{self.period}>"


C = (
    -8.78469475556,
    1.61139411,
    2.33854883889,
    -0.14611605,
    -0.012308094,
    -0.0164248277778,
    0.002211732,
    0.00072546,
    -0.000003582
)