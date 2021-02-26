import os
from datetime import date, datetime

from flask import Flask
from werkzeug.routing import BaseConverter

import rwcwx.routes as r

app = Flask(__name__)
app.config.from_mapping(
    SECRET_KEY=os.getenv("FLASK_SECRET", "_rwcwx_"),
)


class DateStampConverter(BaseConverter):
    FMAT = "%Y%m%d"

    def to_python(self, value: str) -> date:
        return datetime.strptime(value, self.FMAT)

    def to_url(self, value: date) -> str:
        return value.strftime(self.FMAT)


app.url_map.converters["datestamp"] = DateStampConverter

app.add_url_rule("/", view_func=r.todo)
app.add_url_rule("/lol", view_func=r.lol)
app.add_url_rule("/obs/current", view_func=r.current)
app.add_url_rule("/obs/latest", view_func=r.obs_latest)
app.add_url_rule("/obs/summary/day/", view_func=r.day_summary)
app.add_url_rule("/obs/summary/day/<datestamp:d>", view_func=r.day_summary)
