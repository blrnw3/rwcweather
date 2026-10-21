"""Daily sunshine from the weather-API estimate is flagged (api_est) in the daily API rows; webcam days are not."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rwcwx.model import sun as sun_model  # noqa: E402
from rwcwx.models import AvgExt, is_api_estimate  # noqa: E402

API = "API estimate (api:hrrr+asos; calibrated vs webcam, CV MAE 0.9 h); webcam coverage 0%"
BACKFILL = "estimated from 30-min snapshots; coverage 98%"


def _row(var, comment, d=date(2026, 10, 10), val=10.3):
    return AvgExt(d=d, var=var, type="total", period="day", val=val, cnt=None, comment=comment)


def test_is_api_estimate():
    assert is_api_estimate(API) and is_api_estimate("API estimate (api:hrrr; ...)")
    assert not is_api_estimate(BACKFILL) and not is_api_estimate(None) and not is_api_estimate("")


def test_sun_rows_flag_api_estimates_only():
    assert _row("sun", API).simple_dict_ == dict(d=(2026, 10, 10), val=10.3, api_est=True)
    assert "api_est" not in _row("sun", BACKFILL).simple_dict_
    assert "api_est" not in _row("sun", None).simple_dict_
    # Only sunshine carries the flag
    assert "api_est" not in _row("rain", API).simple_dict_


def test_sunpct_days_keep_the_flag():
    days = sun_model.pct_days([_row("sun", API), _row("sun", BACKFILL, d=date(2026, 10, 9), val=11.0)])
    assert days[0].simple_dict_.get("api_est") is True
    assert "api_est" not in days[1].simple_dict_
