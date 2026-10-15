from datetime import time

from rwcwx.calc.record_flags import (
    ON_TRACK, RECORD, TIE, coldest_high, coldest_low, hottest_high, warmest_low,
)


def test_hottest_high_immediate():
    assert hottest_high(30.0, 26.0) == RECORD
    assert hottest_high(26.0, 26.0) == TIE
    assert hottest_high(25.0, 26.0) is None
    assert hottest_high(None, 26.0) is None


def test_coldest_low_immediate():
    assert coldest_low(9.0, 10.7) == RECORD
    assert coldest_low(10.7, 10.7) == TIE
    assert coldest_low(11.0, 10.7) is None


def test_warmest_low_pending_then_final():
    assert warmest_low(15.0, 14.3, time(8, 0)) == ON_TRACK
    assert warmest_low(15.0, 14.3, time(10, 0)) == RECORD
    assert warmest_low(14.3, 14.3, time(10, 0)) == TIE
    assert warmest_low(13.0, 14.3, time(8, 0)) is None  # already colder
    assert warmest_low(13.0, 14.3, time(11, 0)) is None


def test_coldest_high_pending_until_evening():
    assert coldest_high(15.0, 16.6, time(14, 0)) == ON_TRACK
    assert coldest_high(15.0, 16.6, time(18, 0)) == RECORD
    assert coldest_high(16.6, 16.6, time(18, 0)) == TIE
    assert coldest_high(20.0, 16.6, time(14, 0)) is None  # already warmer
