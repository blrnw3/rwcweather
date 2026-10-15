from datetime import date

from rwcwx.calc.rain_freq import frequency_from_rows


def test_exact_years_when_enough_history():
    rows = [
        (date(2021, 10, 15), 0.0),
        (date(2022, 10, 15), 0.02),
        (date(2023, 10, 15), 0.0),
        (date(2024, 10, 15), 0.0),
        (date(2025, 10, 15), 0.01),
        (date(2026, 10, 15), 0.5),  # today — excluded
    ]
    r = frequency_from_rows(rows, date(2026, 10, 15), exclude=date(2026, 10, 15))
    assert r == dict(wet=2, n=5, pct=40.0, smoothed=False, unit="years")


def test_smooth_when_few_years():
    rows = [
        (date(2024, 10, 14), 0.1),
        (date(2024, 10, 15), 0.0),
        (date(2025, 10, 15), 0.0),
        (date(2025, 10, 16), 0.0),
        (date(2026, 10, 15), 0.2),  # excluded
    ]
    r = frequency_from_rows(rows, date(2026, 10, 15), exclude=date(2026, 10, 15), min_years_exact=5)
    assert r["smoothed"] is True and r["unit"] == "days" and r["radius"] == 3
    assert r["n"] == 4 and r["wet"] == 1
    assert date(2026, 10, 15) not in [date(2024, 10, 14)]  # sanity
