from datetime import date, timedelta

from rwcwx.calc.anom_spells import LEVELS, departures, find_anom_spells, level_c, rank_anom_spells
from rwcwx.calc.climate_normal import daily_temp_normal


def test_daily_temp_normal_mid_january_near_monthly():
    # Mid-Jan should be close to January monthly max normal 15.40
    n = daily_temp_normal("max", date(2024, 1, 16))
    assert n is not None and abs(n - 15.40) < 0.5


def test_level_c_and_accepted_levels():
    assert abs(level_c(9) - 5.0) < 1e-9  # 5 °C in °F
    assert 3 in LEVELS and 5 in LEVELS
    # Metric options 2,3,5,7,10 °C accepted as exact °F equivalents
    from rwcwx.calc import anom_spells as m
    assert m.LEVELS_C == (2, 3, 5, 7, 10)
    for c in m.LEVELS_C:
        assert round(c * 9 / 5, 4) in LEVELS
    assert abs(level_c(18) - 10.0) < 1e-9  # 10 °C
    assert abs(level_c(12.6) - 7.0) < 1e-9  # 7 °C


def test_heatwave_spell_from_departures():
    # Synthetic: five days +6 °C above a fake normal by feeding departures directly
    deps = [(date(2024, 7, i), 6.0) for i in range(1, 6)]
    deps += [(date(2024, 7, 6), 0.0)]
    deps += [(date(2024, 7, i), 6.0) for i in range(7, 10)]
    spells = find_anom_spells(deps, 5.0, "above")
    assert [s["length"] for s in spells] == [5, 3]
    assert spells[0]["cum"] == 30.0 and spells[0]["peak"] == 6.0


def test_cold_snap_and_rank_by_peak():
    deps = [(date(2024, 1, i), -4.0) for i in range(1, 4)]
    deps += [(date(2024, 1, i), -8.0) for i in range(10, 12)]
    spells = find_anom_spells(deps, 3.0, "below")
    ranked = rank_anom_spells(spells, "peak", "below", 10)
    assert ranked[0]["length"] == 2 and ranked[0]["peak"] == -8.0


def test_departures_use_normals():
    # Observed = normal → ~0 departure
    d = date(2024, 7, 15)
    n = daily_temp_normal("max", d)
    d2 = d + timedelta(days=1)
    n2 = daily_temp_normal("max", d2)
    series = [(d, n), (d2, n2 + 10)]
    deps = departures(series, "max")
    assert abs(deps[0][1]) < 1e-6 and abs(deps[1][1] - 10) < 1e-6
    assert abs(deps[0][2] - n) < 1e-6 and abs(deps[1][2] - (n2 + 10)) < 1e-6


def test_spell_includes_actual_temps():
    # (date, dep, obs): heatwave days at 30°C (+6), then break, then 28°C (+6)
    deps = [(date(2024, 7, i), 6.0, 30.0) for i in range(1, 4)]
    deps += [(date(2024, 7, 4), 0.0, 24.0)]
    deps += [(date(2024, 7, i), 6.0, 28.0) for i in range(5, 7)]
    spells = find_anom_spells(deps, 5.0, "above")
    assert spells[0]["length"] == 3
    assert abs(spells[0]["mean_temp"] - 30.0) < 1e-6
    assert abs(spells[0]["peak_temp"] - 30.0) < 1e-6
    assert abs(spells[1]["mean_temp"] - 28.0) < 1e-6
    # Cold snap: peak_temp is the coldest (min)
    cold = [(date(2024, 1, i), -5.0, 2.0) for i in range(1, 3)]
    cold += [(date(2024, 1, 3), -8.0, -1.0)]
    spells = find_anom_spells(cold, 3.0, "below")
    assert spells[0]["length"] == 3
    assert abs(spells[0]["mean_temp"] - (2 + 2 + -1) / 3) < 1e-6
    assert abs(spells[0]["peak_temp"] - (-1.0)) < 1e-6
