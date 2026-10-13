"""API sunshine estimates for days without usable webcam data (rwcwx.sun.api_estimate, job/sun_api_backfill)."""
import os
import sys
from datetime import date, timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rwcwx.sun import api_estimate as A  # noqa: E402
from rwcwx.job import sun_api_backfill as J  # noqa: E402


def test_hrrr_dni_hours_local_days_and_gaps():
    payload = {"hourly": {"time": ["2024-06-01T11:00", "2024-06-01T12:00", "2024-06-01T13:00", "2024-06-02T12:00"],
                          "direct_normal_irradiance": [700, 350, 900, None]}}
    assert A.hrrr_dni_hours(payload) == {date(2024, 6, 1): 2.5}


def test_asos_clear_uses_local_daytime():
    # 15:00Z = 08:00 PDT (counted); 14:00Z = 07:00 PDT (not counted)
    rows = ["station,valid,skyc1,skyc2,skyc3", "SQL,2024-06-01 14:00,OVC,M,M"]
    rows += [f"SQL,2024-06-01 {h:02d}:00,{'CLR' if h < 19 else 'BKN'},M,M" for h in range(15, 25) if h < 24]
    got = A.asos_clear("\n".join(rows))
    # 15..18Z CLR (4), 19..23Z BKN (5): mean cover 5*.75/9
    assert abs(got[date(2024, 6, 1)] - round(1 - 5 * 0.75 / 9, 4)) < 1e-9


def test_asos_needs_enough_reports():
    assert A.asos_clear("station,valid,skyc1,skyc2,skyc3\nSQL,2024-06-01 18:00,CLR,M,M") == {}


def _synthetic(n=900, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    d0 = date(2022, 1, 1)
    for i in range(n):
        d = d0 + timedelta(days=i)
        N = 12.0
        truth = rng.uniform(0, 1)
        rows.append(dict(d=d, N=N, hours=truth * N, hrrr_f=0.1 + 0.8 * truth + rng.normal(0, .05),
                         asos_clear=truth + rng.normal(0, .05)))
    return rows


def test_fit_recovers_relation_and_reports_cv():
    f = A.fit(_synthetic(), ("hrrr_f", "asos_clear"), A.NAME_FULL)
    assert f.n == 900 and f.cv_mae_h is not None and f.cv_mae_h < 0.5 and abs(f.cv_bias_h) < 0.1
    assert 0 <= f.frac(dict(hrrr_f=0.9, asos_clear=1.0)) <= 1


def test_estimate_falls_back_without_asos_and_skips_without_hrrr():
    rows = _synthetic()
    full, hrrr = A.fit(rows, ("hrrr_f", "asos_clear"), A.NAME_FULL), A.fit(rows, ("hrrr_f",), A.NAME_HRRR)
    d = date(2024, 1, 1)
    assert A.estimate(d, 10, dict(hrrr_f=0.5, asos_clear=0.5), full, hrrr)["name"] == A.NAME_FULL
    e = A.estimate(d, 10, dict(hrrr_f=0.9, asos_clear=None), full, hrrr)
    assert e["name"] == A.NAME_HRRR and 0 <= e["val"] <= 10
    assert A.estimate(d, 10, dict(hrrr_f=None, asos_clear=0.5), full, hrrr) is None
    c = A.comment_for(e, 63.2)
    assert c.startswith("API estimate (api:hrrr;") and c.endswith("webcam coverage 63.2%")
    assert A.comment_for(e, None).endswith("no webcam total")


def test_plan_targets_missing_and_low_coverage_only():
    t = {
        date(2022, 1, 2): dict(val=5, comment="estimated from 30-min snapshots; coverage 60.0%; scaled", overridden=0),
        date(2022, 1, 3): dict(val=5, comment="estimated from 30-min snapshots; coverage 85.0%; scaled", overridden=0),
        date(2022, 1, 4): dict(val=5, comment="webcam; coverage 40.0%", overridden=0),          # live: never
        date(2022, 1, 5): dict(val=5, comment="estimated from 30-min snapshots; coverage 20.0%", overridden=1),
        date(2022, 1, 6): dict(val=5, comment="hand entered", overridden=0),                     # manual: never
        date(2022, 1, 7): dict(val=5, comment="API estimate (api:hrrr; x); webcam coverage 10.0%", overridden=0),
    }
    got = J.plan(t, date(2022, 1, 1), date(2022, 1, 7), 70.0)
    assert got == {date(2022, 1, 1): None, date(2022, 1, 2): 60.0, date(2022, 1, 7): 10.0}


def test_training_rows_only_full_webcam_days():
    t = {date(2022, 1, 1): dict(val=8, comment="estimated from 30-min snapshots; coverage 100.0%", overridden=0),
         date(2022, 1, 2): dict(val=8, comment="estimated from 30-min snapshots; coverage 80.0%; scaled", overridden=0),
         date(2022, 1, 3): dict(val=8, comment="API estimate (api:hrrr; x); webcam coverage 100.0%", overridden=0)}
    feats = {d: dict(hrrr_f=.5, asos_clear=.5) for d in t}
    assert [r["d"] for r in J.training_rows(t, feats, lambda d: 12.0)] == [date(2022, 1, 1)]


def test_sql_guards_never_touch_live_manual_or_webcam_rows():
    assert "overridden = 0" in J.UPSERT_TOTAL and "comment LIKE 'estimated%'" in J.UPSERT_TOTAL
    assert J.UPSERT_TOTAL.count("comment LIKE 'API estimate%'") == 4
    assert J.UPSERT_ROW.count("IF(source LIKE 'api:%'") == 4 and J.KIND != "sunny"


def test_local_midnight_utc():
    assert J.local_midnight_utc(date(2024, 6, 1)).hour == 7      # PDT
    assert J.local_midnight_utc(date(2024, 1, 1)).hour == 8      # PST
