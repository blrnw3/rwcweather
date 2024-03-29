import os
import time

# Set system TZ (helps for local development; server is always in UTC anyway).
from rwcwx.util import DateStampConverter

os.environ["TZ"] = "UTC"
time.tzset()

from datetime import datetime

from flask import Flask
from flask.json import JSONEncoder

import rwcwx.routes as r


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.timestamp() * 1000
        return JSONEncoder.default(self, obj)


app = Flask(__name__)
app.json_encoder = CustomJSONEncoder
app.config.from_mapping(
    SECRET_KEY=os.getenv("FLASK_SECRET", "_rwcwx_"),
)


@app.after_request
def after_request(response):
    header = response.headers
    header["Access-Control-Allow-Origin"] = "*"
    return response


app.url_map.converters["datestamp"] = DateStampConverter

app.add_url_rule("/api/", view_func=r.todo)
app.add_url_rule("/api/lol", view_func=r.lol)

# Dashboard-optimized
app.add_url_rule("/api/web/dashboard/live", view_func=r.dashboard_live)
app.add_url_rule("/api/web/dashboard/summary", view_func=r.dashboard_summary)

# Live / recent data
app.add_url_rule("/api/obs/current", view_func=r.current)
app.add_url_rule("/api/obs/latest", view_func=r.obs_latest)
app.add_url_rule("/api/obs/trend", view_func=r.trend_live)

# Summaries for all variables at a given aggregate period for a single period
app.add_url_rule("/api/obs/summary/day/<datestamp:d>", view_func=r.day_summary)
app.add_url_rule("/api/obs/summary/month/<datestamp:mnth>", view_func=r.month_summary)
app.add_url_rule("/api/obs/summary/year/<yr>", view_func=r.year_summary)
# Shortcuts to most recent period
app.add_url_rule("/api/obs/summary/day/", view_func=r.day_summary)
app.add_url_rule("/api/obs/summary/month/", view_func=r.month_summary)
app.add_url_rule("/api/obs/summary/year/", view_func=r.year_summary)

# Summaries for a single variable at a given aggregate period for multiple periods
# Note that these take query params to allow filtering on a given year, month, or arbitrary period
app.add_url_rule("/api/var/daily/<var>/<typ>/", view_func=r.var_daily)
app.add_url_rule("/api/var/monthly/<var>/<typ>/", view_func=r.var_monthly)
app.add_url_rule("/api/var/yearly/<var>/<typ>/", view_func=r.var_yearly)
app.add_url_rule("/api/var/all_periods/<var>/<typ>/", view_func=r.var_all_periods)

# Other
app.add_url_rule("/api/astronomy", view_func=r.astronomy)
app.add_url_rule("/api/rain", view_func=r.rain_stats)
