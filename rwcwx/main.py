import os
from datetime import date, datetime

from flask import Flask
from werkzeug.routing import BaseConverter

import rwcwx.routes as r

app = Flask(__name__)
app.config.from_mapping(
    SECRET_KEY=os.getenv("FLASK_SECRET", "_rwcwx_"),
)


@app.after_request
def after_request(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = '*'
    return response


class DateStampConverter(BaseConverter):
    FMAT = "%Y%m%d"

    def to_python(self, value: str) -> date:
        return datetime.strptime(value, self.FMAT)

    def to_url(self, value: date) -> str:
        return value.strftime(self.FMAT)


app.url_map.converters["datestamp"] = DateStampConverter

app.add_url_rule("/api/", view_func=r.todo)
app.add_url_rule("/api/lol", view_func=r.lol)
app.add_url_rule("/api/web/dashboard", view_func=r.dashboard)
app.add_url_rule("/api/obs/current", view_func=r.current)
app.add_url_rule("/api/obs/latest", view_func=r.obs_latest)
app.add_url_rule("/api/obs/trend", view_func=r.trend_live)
app.add_url_rule("/api/obs/summary/day/", view_func=r.day_summary)
app.add_url_rule("/api/obs/summary/day/<datestamp:d>", view_func=r.day_summary)
