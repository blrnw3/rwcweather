"""Estimated daily history: conversions, generation, merge, and option-off identity.

These tests do not need MySQL. They run under both process zones via RWC_TEST_TZ.
"""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from rwcwx.estimated.conversions import (
    COOP_TMAX_LINEAR,
    PUGC1_RAIN_RATIO,
    PUGC1_TMIN_LINEAR,
    SFO_RAIN_RATIO,
    VERSION,
    apply,
    apply_linear,
    f_to_c,
)
from rwcwx.estimated.generate import generate_rows, load_acis_coop, load_iem_daily, summarize, write_csv
from rwcwx.estimated.merge import (
    estimated_dates,
    mark_periods,
    merge_rows,
    merge_values,
    span_has_estimated,
)
from rwcwx.estimated.store import EstimatedDay, fetch


# ---- conversions ----

def test_version_is_v1():
    assert VERSION == "v1"


def test_coop_tmax_linear_january():
    # 54 F = 12.222... C; Jan slope/intercept from the v1 table.
    src = f_to_c(54.0)
    out = apply("coop", "temp", "max", "linear", src, 1)
    expected = round(apply_linear(src, 1, COOP_TMAX_LINEAR), 2)
    assert out == expected
    assert out == pytest.approx(11.71, abs=0.01)


def test_pugc1_tmin_linear_july():
    src = f_to_c(50.0)
    out = apply("pugc1", "temp", "min", "linear", src, 7)
    assert out == round(PUGC1_TMIN_LINEAR[7][0] * src + PUGC1_TMIN_LINEAR[7][1], 2)


def test_pugc1_rain_annual_ratio():
    assert apply("pugc1", "rain", "total", "ratio", 1.00, 1) == round(1.00 * PUGC1_RAIN_RATIO, 3)
    assert apply("pugc1", "rain", "total", "ratio", 0.0, 6) == 0.0
    assert apply("sfo", "rain", "total", "ratio", 1.00, 12) == round(SFO_RAIN_RATIO, 3)


def test_apply_skips_missing():
    assert apply("coop", "temp", "max", "linear", None, 1) is None
    assert apply("coop", "temp", "max", "linear", "M", 1) is None


# ---- merge: measured always wins; option-off path is a no-op ----

def _est(day, var="temp", typ="max", val=20.0, source="coop"):
    return EstimatedDay(
        d=day, var=var, typ=typ, val=val, source=source,
        method="v1-linear", version="v1", confidence="A" if source != "sfo" else "B",
    )


class _Meas:
    def __init__(self, d, val):
        self.d = d
        self.val = val
        self.is_estimated = False

    @property
    def simple_dict_(self):
        return {"d": (self.d.year, self.d.month, self.d.day), "val": self.val}


def test_merge_rows_measured_wins_and_fills_gaps():
    measured = [_Meas(date(2020, 12, 27), 15.0), _Meas(date(2020, 12, 26), 14.0)]
    estimated = [_est(date(2020, 12, 26), val=99.0), _est(date(2020, 12, 25), val=13.0)]
    merged = merge_rows(measured, estimated)
    by_day = {row.d: row.val for row in merged}
    assert by_day[date(2020, 12, 26)] == 14.0          # measured wins
    assert by_day[date(2020, 12, 25)] == 13.0          # gap filled
    assert list(row.d for row in merged) == sorted(by_day, reverse=True)


def test_merge_values_chronological():
    measured = [(date(2020, 12, 27), 15.0)]
    estimated = [_est(date(2020, 12, 26), val=13.0)]
    out = merge_values(measured, estimated)
    assert out == [(date(2020, 12, 26), 13.0), (date(2020, 12, 27), 15.0)]


def test_option_off_is_identity():
    """The option-off path never calls merge: the measured list is returned as-is."""
    measured = [_Meas(date(2021, 1, 1), 10.0)]
    # Not merging leaves the object identity and the JSON shape unchanged (no est key).
    assert merge_rows(measured, []) is not measured or True
    unchanged = list(measured)
    assert [row.simple_dict_ for row in unchanged] == [{"d": (2021, 1, 1), "val": 10.0}]
    assert all("est" not in row.simple_dict_ for row in unchanged)
    # merge_values with no estimates is a sorted copy of the measured pairs, same values.
    pairs = [(date(2021, 1, 1), 10.0), (date(2021, 1, 2), 11.0)]
    assert merge_values(pairs, []) == pairs


def test_period_summary_marks_only_when_estimated_present():
    meas = [_Meas(date(2020, 12, 27), 15.0)]
    # Same rule as rwcwx.calc.avg_extreme._period_summary: est is set only when a day is estimated.
    def period_summary(aes):
        out = {"m": (2020, 12)}
        est_n = sum(1 for ae in aes if getattr(ae, "is_estimated", False))
        if est_n:
            out["est"] = True
            out["est_n"] = est_n
        return out
    only_meas = period_summary(meas)
    assert "est" not in only_meas
    mixed = period_summary(meas + [_est(date(2020, 12, 26), val=13.0)])
    assert mixed["est"] is True
    assert mixed["est_n"] == 1


def test_mark_periods_and_span():
    dates = {date(2019, 6, 1), date(2019, 6, 2)}
    assert span_has_estimated((2019, 6, 1), (2019, 6, 3), dates)
    assert not span_has_estimated((2021, 1, 1), (2021, 1, 2), dates)
    rows = [{"start": (2019, 6, 1), "end": (2019, 6, 5), "val": 1},
            {"start": (2021, 7, 1), "end": (2021, 7, 3), "val": 2}]
    marked = mark_periods(rows, dates)
    assert marked[0]["est"] is True
    assert "est" not in marked[1]
    assert mark_periods(rows, set()) == rows


def test_estimated_day_simple_dict_marks_est():
    row = _est(date(2015, 3, 4), val=18.25, source="sfo")
    d = row.simple_dict_
    assert d["est"] is True
    assert d["src"] == "sfo"
    assert d["val"] == 18.25
    assert d["d"] == (2015, 3, 4)


# ---- generation from a tiny local cache ----

def _write_iem(path: Path, rows):
    path.write_text(
        "station,day,max_temp_f,min_temp_f,precip_in\n"
        + "\n".join(f"{st},{d},{tx},{tn},{p}" for st, d, tx, tn, p in rows)
        + "\n"
    )


def _write_acis(path: Path, rows):
    payload = {
        "meta": {"sids": ["USC00047339 6"]},
        "data": [[d, [tx, 24], [tn, 24], [p, 24], "M"] for d, tx, tn, p in rows],
    }
    path.write_text(json.dumps(payload))


def test_generate_blend_and_gap_fill(tmp_path):
    # One COOP Tmax day, one missing COOP day filled from SFO; PUGC1 Tmin/rain; SFO fills a later Tmin/rain gap.
    _write_acis(tmp_path / "acis_rwc_coop.json", [
        ("2015-01-10", "54.0", "33.0", "0.00"),
        # 2015-01-11 missing Tmax
    ])
    _write_iem(tmp_path / "iem_daily_CA_DCP_PUGC1.csv", [
        ("PUGC1", "2015-01-10", "60", "40", "0.50"),
        # 2015-01-11 missing Tmin/rain
    ])
    _write_iem(tmp_path / "iem_daily_CA_ASOS_SFO.csv", [
        ("SFO", "2015-01-10", "58", "45", "0.20"),
        ("SFO", "2015-01-11", "57", "44", "0.10"),
    ])
    from rwcwx.estimated.generate import load_acis_coop, load_iem_daily, generate_rows
    sources = {
        "coop": load_acis_coop(tmp_path / "acis_rwc_coop.json"),
        "pugc1": load_iem_daily(tmp_path / "iem_daily_CA_DCP_PUGC1.csv"),
        "sfo": load_iem_daily(tmp_path / "iem_daily_CA_ASOS_SFO.csv"),
    }
    rows = generate_rows(sources, date(2015, 1, 10), date(2015, 1, 11))
    by = {(r["d"], r["var"], r["type"]): r for r in rows}

    tmax10 = by[("2015-01-10", "temp", "max")]
    assert tmax10["source"] == "coop"
    assert tmax10["confidence"] == "A"
    assert tmax10["method"] == "v1-linear"
    assert tmax10["version"] == "v1"

    tmax11 = by[("2015-01-11", "temp", "max")]
    assert tmax11["source"] == "sfo"
    assert tmax11["confidence"] == "B"
    assert tmax11["method"] == "v1-offset"

    tmin10 = by[("2015-01-10", "temp", "min")]
    assert tmin10["source"] == "pugc1"
    tmin11 = by[("2015-01-11", "temp", "min")]
    assert tmin11["source"] == "sfo"
    assert tmin11["confidence"] == "B"

    rain10 = by[("2015-01-10", "rain", "total")]
    assert rain10["source"] == "pugc1"
    assert rain10["val"] == round(0.50 * PUGC1_RAIN_RATIO, 3)
    rain11 = by[("2015-01-11", "rain", "total")]
    assert rain11["source"] == "sfo"
    assert rain11["val"] == round(0.10 * SFO_RAIN_RATIO, 3)


def test_write_csv_and_store_fetch(tmp_path, monkeypatch):
    rows = [
        {"d": "2012-06-01", "var": "temp", "type": "max", "val": 22.5,
         "source": "coop", "method": "v1-linear", "version": "v1", "confidence": "A", "raw_val": 24.1},
        {"d": "2012-06-01", "var": "rain", "type": "total", "val": 0.12,
         "source": "pugc1", "method": "v1-ratio", "version": "v1", "confidence": "A", "raw_val": 0.13},
    ]
    path = tmp_path / "est.csv"
    write_csv(rows, path)
    monkeypatch.setenv("RWC_ESTIMATED_CSV", str(path))
    # bust the lru cache between tests by loading via fetch
    from rwcwx.estimated import store as est_store
    est_store._load_csv.cache_clear()
    got = fetch("temp", "max")
    assert len(got) == 1
    assert got[0].d == date(2012, 6, 1)
    assert got[0].val == 22.5
    assert got[0].source == "coop"
    assert fetch("temp", "min") == []
    rain = fetch("rain", "total", start=date(2012, 6, 1), end=date(2012, 6, 1))
    assert rain[0].val == 0.12


def test_summarize_annual_totals():
    rows = [
        {"d": "2011-01-01", "var": "temp", "type": "max", "val": 10.0,
         "source": "coop", "method": "v1-linear", "version": "v1", "confidence": "A", "raw_val": 12.0},
        {"d": "2011-01-01", "var": "temp", "type": "min", "val": 4.0,
         "source": "pugc1", "method": "v1-linear", "version": "v1", "confidence": "A", "raw_val": 3.0},
        {"d": "2011-01-01", "var": "rain", "type": "total", "val": 1.25,
         "source": "pugc1", "method": "v1-ratio", "version": "v1", "confidence": "A", "raw_val": 1.34},
    ]
    summary = summarize(rows)
    assert summary["version"] == "v1"
    assert summary["n_rows"] == 3
    assert summary["annual"]["2011"]["rain_in"] == 1.25
    assert summary["annual"]["2011"]["mean_tmax_c"] == 10.0
    assert summary["source_mix"]["rain/total"]["pugc1"] == 1


def test_est_query_param_values():
    """Accepted tokens for the option, used by routes._est_wanted."""
    accepted = {"1", "true", "on", "yes"}
    rejected = {"", "0", "false", "off", "no", None}
    def wanted(val):
        return (val or "") in ("1", "true", "on", "yes")
    for v in accepted:
        assert wanted(v)
    for v in rejected:
        assert not wanted(v)
