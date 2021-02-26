import os

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Numeric, DateTime


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
    solr = Column()
    pm2 = Column()
    wet = Column()
    sun = Column()
    inhumi = Column()
    intemp = Column()
    t_obs = Column()
