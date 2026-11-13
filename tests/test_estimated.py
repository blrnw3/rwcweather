"""Estimated daily history: conversions, generation, merge, and option-off identity.

These tests do not need MySQL. They run under both process zones via RWC_TEST_TZ.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from rwcwx.estimated.conversions import (
    COOP_RAIN_RATIO,
    COOP_TMAX_LINEAR,
    PUGC1_RAIN_RATIO,
    PUGC1_TMAX_LINEAR,
    PUGC1_TMIN_LINEAR,
    SFO_RAIN_RATIO,
    VERSION,
    apply,
    apply_linear,
    confidence_for,
    f_to_c,
)
from rwcwx.estimated.generate import generate_rows, load_acis_coop, load_iem_daily, summarize, write_csv
from rwcwx.estimated.merge import (
    mark_periods,
    merge_rows,
    merge_values,
    span_has_estimated,
)
from rwcwx.estimated.store import EstimatedDay, fetch


# ---- conversions ----

def test_version_is_v5():
    assert VERSION == "v5"


def test_pugc1_tmax_linear_january():
    src = f_to_c(60.0)
    out = apply("pugc1", "temp", "max", "linear", src, 1)
    expected = round(apply_linear(src, 1, PUGC1_TMAX_LINEAR), 2)
    assert out == expected
    assert out == pytest.approx(14.10, abs=0.01)


def test_coop_tmax_linear_january():
    src = f_to_c(54.0)
    out = apply("coop", "temp", "max", "linear", src, 1)
    expected = round(apply_linear(src, 1, COOP_TMAX_LINEAR), 2)
    assert out == expected
    assert out == pytest.approx(11.71, abs=0.01)


def test_pugc1_tmin_linear_july():
    src = f_to_c(50.0)
    out = apply("pugc1", "temp", "min", "linear", src, 7)
    assert out == round(PUGC1_TMIN_LINEAR[7][0] * src + PUGC1_TMIN_LINEAR[7][1], 2)


def test_rain_annual_ratios():
    assert apply("pugc1", "rain", "total", "ratio", 1.00, 1) == round(1.00 * PUGC1_RAIN_RATIO, 3)
    assert apply("pugc1", "rain", "total", "ratio", 0.0, 6) == 0.0
    assert apply("coop", "rain", "total", "ratio", 1.00, 3) == round(COOP_RAIN_RATIO, 3)
    assert apply("sfo", "rain", "total", "ratio", 1.00, 12) == round(SFO_RAIN_RATIO, 3)


def test_apply_skips_missing():
    assert apply("pugc1", "temp", "max", "linear", None, 1) is None
    assert apply("coop", "temp", "max", "linear", "M", 1) is None


def test_confidence_by_source():
    assert confidence_for("pugc1") == "A"
    assert confidence_for("coop") == "B"
    assert confidence_for("sfo") == "C"


# ---- merge: measured always wins; option-off path is a no-op ----

def _est(day, var="temp", typ="max", val=20.0, source="pugc1"):
    conf = {"pugc1": "A", "coop": "B", "sfo": "C"}.get(source, "A")
    return EstimatedDay(
        d=day, var=var, typ=typ, val=val, source=source,
        method="v5-linear", version="v5", confidence=conf,
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
    unchanged = list(measured)
    assert [row.simple_dict_ for row in unchanged] == [{"d": (2021, 1, 1), "val": 10.0}]
    assert all("est" not in row.simple_dict_ for row in unchanged)
    pairs = [(date(2021, 1, 1), 10.0), (date(2021, 1, 2), 11.0)]
    assert merge_values(pairs, []) == pairs


def test_period_summary_marks_only_when_estimated_present():
    meas = [_Meas(date(2020, 12, 27), 15.0)]
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
    row = _est(date(2015, 3, 4), val=18.25, source="coop")
    d = row.simple_dict_
    assert d["est"] is True
    assert d["src"] == "coop"
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
    path.write_text(__import__("json").dumps(payload))


def test_generate_pulgas_primary_then_gap_fill(tmp_path):
    # Day 10: all three variables from Pulgas.
    # Day 11: Pulgas Tmax missing -> COOP; Pulgas Tmin/rain missing -> COOP.
    # Day 12: Pulgas and COOP missing Tmax -> SFO; Tmin from SFO; rain from SFO.
    # Day 13: nothing from any source -> no rows.
    _write_iem(tmp_path / "iem_daily_CA_DCP_PUGC1.csv", [
        ("PUGC1", "2015-01-10", "60", "40", "0.50"),
        ("PUGC1", "2015-01-11", "M", "M", "M"),
    ])
    _write_acis(tmp_path / "acis_rwc_coop.json", [
        ("2015-01-10", "54.0", "33.0", "0.00"),
        ("2015-01-11", "54.0", "33.0", "0.20"),
    ])
    _write_iem(tmp_path / "iem_daily_CA_ASOS_SFO.csv", [
        ("SFO", "2015-01-10", "58", "45", "0.20"),
        ("SFO", "2015-01-11", "57", "44", "0.10"),
        ("SFO", "2015-01-12", "57", "44", "0.10"),
    ])
    sources = {
        "pugc1": load_iem_daily(tmp_path / "iem_daily_CA_DCP_PUGC1.csv"),
        "coop": load_acis_coop(tmp_path / "acis_rwc_coop.json"),
        "sfo": load_iem_daily(tmp_path / "iem_daily_CA_ASOS_SFO.csv"),
    }
    rows = generate_rows(sources, date(2015, 1, 10), date(2015, 1, 13))
    by = {(r["d"], r["var"], r["type"]): r for r in rows}

    tmax10 = by[("2015-01-10", "temp", "max")]
    assert tmax10["source"] == "pugc1"
    assert tmax10["confidence"] == "A"
    assert tmax10["method"] == "v5-linear"
    assert tmax10["version"] == "v5"
    assert tmax10["val"] == apply("pugc1", "temp", "max", "linear", f_to_c(60.0), 1)

    tmin10 = by[("2015-01-10", "temp", "min")]
    assert tmin10["source"] == "pugc1"
    rain10 = by[("2015-01-10", "rain", "total")]
    assert rain10["source"] == "pugc1"
    assert rain10["val"] == round(0.50 * PUGC1_RAIN_RATIO, 3)

    tmax11 = by[("2015-01-11", "temp", "max")]
    assert tmax11["source"] == "coop"
    assert tmax11["confidence"] == "B"
    assert tmax11["method"] == "v5-linear"
    tmin11 = by[("2015-01-11", "temp", "min")]
    assert tmin11["source"] == "coop"
    assert tmin11["confidence"] == "B"
    rain11 = by[("2015-01-11", "rain", "total")]
    assert rain11["source"] == "coop"
    assert rain11["val"] == round(0.20 * COOP_RAIN_RATIO, 3)

    tmax12 = by[("2015-01-12", "temp", "max")]
    assert tmax12["source"] == "sfo"
    assert tmax12["confidence"] == "C"
    assert tmax12["method"] == "v5-offset"
    tmin12 = by[("2015-01-12", "temp", "min")]
    assert tmin12["source"] == "sfo"
    assert tmin12["confidence"] == "C"
    assert tmin12["method"] == "v5-linear"
    rain12 = by[("2015-01-12", "rain", "total")]
    assert rain12["source"] == "sfo"
    assert rain12["val"] == round(0.10 * SFO_RAIN_RATIO, 3)

    assert not any(r["d"] == "2015-01-13" for r in rows)


def test_write_csv_and_store_fetch(tmp_path, monkeypatch):
    rows = [
        {"d": "2012-06-01", "var": "temp", "type": "max", "val": 22.5,
         "source": "pugc1", "method": "v5-linear", "version": "v5", "confidence": "A", "raw_val": 24.1},
        {"d": "2012-06-01", "var": "rain", "type": "total", "val": 0.12,
         "source": "coop", "method": "v5-ratio", "version": "v5", "confidence": "B", "raw_val": 0.10},
    ]
    path = tmp_path / "est.csv"
    write_csv(rows, path)
    monkeypatch.setenv("RWC_ESTIMATED_CSV", str(path))
    from rwcwx.estimated import store as est_store
    est_store._load_csv.cache_clear()
    got = fetch("temp", "max")
    assert len(got) == 1
    assert got[0].d == date(2012, 6, 1)
    assert got[0].val == 22.5
    assert got[0].source == "pugc1"
    assert fetch("temp", "min") == []
    rain = fetch("rain", "total", start=date(2012, 6, 1), end=date(2012, 6, 1))
    assert rain[0].val == 0.12
    assert rain[0].source == "coop"
    assert rain[0].confidence == "B"


def test_summarize_annual_totals_and_fill_share():
    rows = [
        {"d": "2011-01-01", "var": "temp", "type": "max", "val": 10.0,
         "source": "pugc1", "method": "v5-linear", "version": "v5", "confidence": "A", "raw_val": 12.0},
        {"d": "2011-01-02", "var": "temp", "type": "max", "val": 11.0,
         "source": "coop", "method": "v5-linear", "version": "v5", "confidence": "B", "raw_val": 13.0},
        {"d": "2011-01-01", "var": "temp", "type": "min", "val": 4.0,
         "source": "pugc1", "method": "v5-linear", "version": "v5", "confidence": "A", "raw_val": 3.0},
        {"d": "2011-01-01", "var": "rain", "type": "total", "val": 1.25,
         "source": "pugc1", "method": "v5-ratio", "version": "v5", "confidence": "A", "raw_val": 1.34},
    ]
    summary = summarize(rows, date(2011, 1, 1), date(2011, 1, 2))
    assert summary["version"] == "v5"
    assert summary["n_rows"] == 4
    assert summary["annual"]["2011"]["rain_in"] == 1.25
    assert summary["annual"]["2011"]["mean_tmax_c"] == 10.5
    assert summary["annual"]["2011"]["missing_tmax"] == 0
    assert summary["annual"]["2011"]["missing_tmin"] == 1
    assert summary["annual"]["2011"]["tmax_secondary"] == 1
    assert summary["annual"]["2011"]["tmax_coop"] == 1
    assert summary["source_mix"]["temp/max"]["pugc1"] == 1
    assert summary["source_mix"]["temp/max"]["coop"] == 1
    assert summary["fill_share"]["temp/max"]["2011"]["pct_secondary"] == 50.0


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


# ---- quality control of Pulgas primaries ----

from rwcwx.estimated.qc import rain_is_bogus, tmax_is_bogus, tmin_is_bogus


def test_qc_rain_rules():
    # Spike vs dry peers
    assert rain_is_bogus(9.54, 0.0, 0.0)
    assert rain_is_bogus(5.75, 0.0, 0.0)
    # Greater than 3× the larger peer
    assert rain_is_bogus(1.09, 0.30, 0.29)
    # Real storm: peers agree
    assert not rain_is_bogus(4.18, 4.19, 3.43)
    # Below the 1 in threshold, even if peers are dry
    assert not rain_is_bogus(0.90, 0.0, 0.0)
    # No comparators: cannot reject
    assert not rain_is_bogus(5.75, None, None)
    # Exactly at 3× is kept (rule is strictly greater than)
    assert not rain_is_bogus(1.50, 0.50, 0.40)


def test_qc_tmin_rules():
    # Disagrees with COOP (SFO unused when COOP exists)
    assert tmin_is_bogus(-5.79, 8.09, 7.5)
    assert not tmin_is_bogus(14.1, 12.0, 13.0)
    # Prefer COOP even if SFO also exists
    assert not tmin_is_bogus(20.0, 16.0, 1.0)
    assert tmin_is_bogus(20.0, 11.9, 20.0)
    # No comparators: cannot reject
    assert not tmin_is_bogus(30.0, None, None)
    # Fall back to SFO when COOP is missing
    assert tmin_is_bogus(20.0, None, 11.9)
    # Exactly 8 °C is kept
    assert not tmin_is_bogus(20.0, 12.0, None)


def test_qc_tmax_requires_both_peers():
    # Both COOP and SFO disagree
    assert tmax_is_bogus(31.41, 21.57, 20.29)
    # Disagrees with COOP but SFO is within 8 °C: keep Pulgas
    assert not tmax_is_bogus(26.51, 18.23, 19.73)
    assert not tmax_is_bogus(30.08, 17.68, 26.0)
    # SFO missing: keep Pulgas even if COOP disagrees
    assert not tmax_is_bogus(31.41, 21.57, None)
    # COOP missing: keep Pulgas even if SFO disagrees
    assert not tmax_is_bogus(31.41, None, 20.29)
    # No comparators
    assert not tmax_is_bogus(31.41, None, None)
    # Exactly 8 °C from either peer is kept
    assert not tmax_is_bogus(20.0, 12.0, 11.9)
    assert not tmax_is_bogus(20.0, 11.9, 12.0)


def test_generate_rejects_bogus_pulgas_rain_and_temp(tmp_path):
    # 10th: huge Pulgas rain while COOP/SFO are dry; also a wild Pulgas Tmin.
    # 11th: a real storm (peers agree) and ordinary temperatures, kept.
    # 12th: modest Pulgas rain below 1 in on a dry day, kept.
    _write_iem(tmp_path / "iem_daily_CA_DCP_PUGC1.csv", [
        ("PUGC1", "2015-01-10", "60", "14", "9.54"),   # 14 F ≈ -10 °C
        ("PUGC1", "2015-01-11", "60", "40", "4.18"),
        ("PUGC1", "2015-01-12", "60", "40", "0.90"),
    ])
    _write_acis(tmp_path / "acis_rwc_coop.json", [
        ("2015-01-10", "54.0", "42.0", "0.00"),
        ("2015-01-11", "54.0", "42.0", "4.19"),
        ("2015-01-12", "54.0", "42.0", "0.00"),
    ])
    _write_iem(tmp_path / "iem_daily_CA_ASOS_SFO.csv", [
        ("SFO", "2015-01-10", "58", "45", "0.00"),
        ("SFO", "2015-01-11", "58", "45", "3.43"),
        ("SFO", "2015-01-12", "58", "45", "0.00"),
    ])
    sources = {
        "pugc1": load_iem_daily(tmp_path / "iem_daily_CA_DCP_PUGC1.csv"),
        "coop": load_acis_coop(tmp_path / "acis_rwc_coop.json"),
        "sfo": load_iem_daily(tmp_path / "iem_daily_CA_ASOS_SFO.csv"),
    }
    rejections = []
    rows = generate_rows(sources, date(2015, 1, 10), date(2015, 1, 12), rejections)
    by = {(r["d"], r["var"], r["type"]): r for r in rows}

    rain10 = by[("2015-01-10", "rain", "total")]
    assert rain10["source"] == "coop"
    assert rain10["confidence"] == "B"
    assert rain10["val"] == 0.0
    assert rain10["version"] == "v5"

    tmin10 = by[("2015-01-10", "temp", "min")]
    assert tmin10["source"] == "coop"
    assert tmin10["confidence"] == "B"
    assert tmin10["val"] == apply("coop", "temp", "min", "linear", f_to_c(42.0), 1)

    tmax10 = by[("2015-01-10", "temp", "max")]
    assert tmax10["source"] == "pugc1"
    assert tmax10["confidence"] == "A"

    rain11 = by[("2015-01-11", "rain", "total")]
    assert rain11["source"] == "pugc1"
    assert rain11["val"] == round(4.18 * PUGC1_RAIN_RATIO, 3)

    rain12 = by[("2015-01-12", "rain", "total")]
    assert rain12["source"] == "pugc1"
    assert rain12["val"] == round(0.90 * PUGC1_RAIN_RATIO, 3)

    by_rej = {(r["d"], r["var"], r["type"]): r for r in rejections}
    assert set(by_rej) == {("2015-01-10", "rain", "total"), ("2015-01-10", "temp", "min")}
    rain_rej = by_rej[("2015-01-10", "rain", "total")]
    assert rain_rej["rejected_raw"] == 9.54
    assert rain_rej["rejected_val"] == round(9.54 * PUGC1_RAIN_RATIO, 3)
    assert rain_rej["reason"] == "rain_spike"
    assert rain_rej["replacement_source"] == "coop"
    assert rain_rej["replacement_val"] == 0.0
    assert rain_rej["replacement_confidence"] == "B"
    tmin_rej = by_rej[("2015-01-10", "temp", "min")]
    assert tmin_rej["reason"] == "temp_outlier"
    assert tmin_rej["replacement_source"] == "coop"
    assert tmin_rej["rejected_raw"] == f_to_c(14.0)

    summary = summarize(rows, date(2015, 1, 10), date(2015, 1, 12), rejections)
    assert summary["n_rejections"] == 2
    assert len(summary["rejections"]) == 2


def test_generate_keeps_pulgas_rain_when_no_comparators(tmp_path):
    _write_iem(tmp_path / "iem_daily_CA_DCP_PUGC1.csv", [
        ("PUGC1", "2015-01-10", "60", "40", "5.75"),
    ])
    sources = {
        "pugc1": load_iem_daily(tmp_path / "iem_daily_CA_DCP_PUGC1.csv"),
        "coop": {},
        "sfo": {},
    }
    rejections = []
    rows = generate_rows(sources, date(2015, 1, 10), date(2015, 1, 10), rejections)
    rain = [r for r in rows if r["var"] == "rain"][0]
    assert rain["source"] == "pugc1"
    assert rain["val"] == round(5.75 * PUGC1_RAIN_RATIO, 3)
    assert rejections == []


def test_generate_tmax_rejected_only_when_sfo_also_disagrees(tmp_path):
    # 10th: Pulgas Tmax far from COOP but close to SFO -> keep Pulgas.
    # 11th: Pulgas Tmax far from both -> reject, fill from COOP.
    # 12th: Pulgas Tmax far from COOP, SFO missing -> keep Pulgas.
    _write_iem(tmp_path / "iem_daily_CA_DCP_PUGC1.csv", [
        ("PUGC1", "2015-05-10", "90", "50", "0.00"),
        ("PUGC1", "2015-05-11", "90", "50", "0.00"),
        ("PUGC1", "2015-05-12", "90", "50", "0.00"),
    ])
    _write_acis(tmp_path / "acis_rwc_coop.json", [
        ("2015-05-10", "54.0", "42.0", "0.00"),
        ("2015-05-11", "54.0", "42.0", "0.00"),
        ("2015-05-12", "54.0", "42.0", "0.00"),
    ])
    _write_iem(tmp_path / "iem_daily_CA_ASOS_SFO.csv", [
        ("SFO", "2015-05-10", "90", "50", "0.00"),
        ("SFO", "2015-05-11", "58", "45", "0.00"),
        # 12th: no SFO row
    ])
    sources = {
        "pugc1": load_iem_daily(tmp_path / "iem_daily_CA_DCP_PUGC1.csv"),
        "coop": load_acis_coop(tmp_path / "acis_rwc_coop.json"),
        "sfo": load_iem_daily(tmp_path / "iem_daily_CA_ASOS_SFO.csv"),
    }
    rejections = []
    rows = generate_rows(sources, date(2015, 5, 10), date(2015, 5, 12), rejections)
    by = {(r["d"], r["var"], r["type"]): r for r in rows}

    pug_tmax = apply("pugc1", "temp", "max", "linear", f_to_c(90.0), 5)
    coop_tmax = apply("coop", "temp", "max", "linear", f_to_c(54.0), 5)
    sfo_agree = apply("sfo", "temp", "max", "offset", f_to_c(90.0), 5)
    sfo_disagree = apply("sfo", "temp", "max", "offset", f_to_c(58.0), 5)
    assert abs(pug_tmax - coop_tmax) > 8
    assert abs(pug_tmax - sfo_agree) <= 8
    assert abs(pug_tmax - sfo_disagree) > 8

    assert by[("2015-05-10", "temp", "max")]["source"] == "pugc1"
    assert by[("2015-05-10", "temp", "max")]["val"] == pug_tmax

    tmax11 = by[("2015-05-11", "temp", "max")]
    assert tmax11["source"] == "coop"
    assert tmax11["confidence"] == "B"
    assert tmax11["val"] == coop_tmax

    assert by[("2015-05-12", "temp", "max")]["source"] == "pugc1"
    assert by[("2015-05-12", "temp", "max")]["val"] == pug_tmax

    by_rej = {(r["d"], r["var"], r["type"]): r for r in rejections}
    assert set(by_rej) == {("2015-05-11", "temp", "max")}
    rej = by_rej[("2015-05-11", "temp", "max")]
    assert rej["reason"] == "temp_outlier"
    assert rej["rejected_val"] == pug_tmax
    assert rej["replacement_source"] == "coop"
    assert rej["replacement_val"] == coop_tmax
    assert rej["replacement_confidence"] == "B"
