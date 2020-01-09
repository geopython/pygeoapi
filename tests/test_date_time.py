# =================================================================
#
# Authors: Timo Tuunanen <timo.tuunanen@rdvelho.com>
#
# Copyright (c) 2020 Timo Tuunanen
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

import pytest
from pygeoapi.date_time import parse, DatetimeRange
from datetime import datetime, timedelta, timezone
from typing import Tuple


def daterange(start: Tuple[int], end: Tuple[int]):
    return DatetimeRange(datetime(*start), datetime(*end))


utc = timezone.utc
tz02 = timezone(timedelta(hours=2))
tz0530 = timezone(timedelta(hours=5, minutes=30))
tz08n = timezone(-timedelta(hours=8))


def test_date():
    assert parse('2001-02-03') == (
        daterange((2001, 2, 3, 0, 0, 0),
                  (2001, 2, 4, 0, 0, 0)))
    assert parse('2001-02') == (
        daterange((2001, 2, 1, 0, 0, 0),
                  (2001, 3, 1, 0, 0, 0)))
    assert parse('2001') == (
        daterange((2001, 1, 1, 0, 0, 0),
                  (2002, 1, 1, 0, 0, 0)))


def test_datetime():
    assert parse('2001-02-03T12:34:56') == (
        daterange((2001, 2, 3, 12, 34, 56),
                  (2001, 2, 3, 12, 34, 57)))


def test_microsecond():
    assert parse('2001-02-03T12:34:56.789') == (
        daterange((2001, 2, 3, 12, 34, 56, 789000),
                  (2001, 2, 3, 12, 34, 56, 790000)))
    assert parse('2001-02-03T12:34:56.987654') == (
        daterange((2001, 2, 3, 12, 34, 56, 987654),
                  (2001, 2, 3, 12, 34, 56, 987655)))


def test_microsecond_limits():
    assert parse('2001-12-31T23:59:59.999999') == (
        daterange((2001, 12, 31, 23, 59, 59, 999999),
                  (2002, 1, 1, 0, 0, 0, 000000)))
    assert parse('2001-12-31T23:59:59.999') == (
        daterange((2001, 12, 31, 23, 59, 59, 999000),
                  (2002, 1, 1, 0, 0, 0, 000000)))


def test_range():
    assert parse('2001-02-03T13:00:00/2002-12-24T15:30:00') == (
        daterange((2001, 2, 3, 13, 0, 0),
                  (2002, 12, 24, 15, 30, 1)))


def test_range_partials():
    assert parse('2001-02-03T13:00:00/15:00') == (
        daterange((2001, 2, 3, 13, 0, 0),
                  (2001, 2, 3, 15, 1)))
    assert parse('2001-02-03T13:00:00/2007-04-01') == (
        daterange((2001, 2, 3, 13, 0, 0),
                  (2007, 4, 2, 0, 0, 0)))
    assert parse('2001-02-03/15T24:00') == (
        daterange((2001, 2, 3, 0, 0, 0),
                  (2001, 2, 16, 0, 0, 0)))
    assert parse('2001-02-03/T24') == (
        daterange((2001, 2, 3, 0, 0, 0),
                  (2001, 2, 4, 0, 0, 0)))
    assert parse('2001-02-03/T24:02') == (
        daterange((2001, 2, 3, 0, 0, 0),
                  (2001, 2, 4, 0, 3, 0)))


def test_range_with_open_ends():
    assert parse('2001-02-03T13:00:00/..').end is None
    assert parse('../2001-02-03T13:00:00').start is None


def test_timezone():
    assert parse('2001-02-03T12:34:56Z') == (
        daterange((2001, 2, 3, 12, 34, 56, 0, utc),
                  (2001, 2, 3, 12, 34, 57, 0, utc)))
    assert parse('2001-02-03T12:34:56+02').start == (
        datetime(2001, 2, 3, 12, 34, 56, 0, tz02))
    assert parse('2001-02-03T12:34:56+0530').start == (
        datetime(2001, 2, 3, 12, 34, 56, 0, tz0530))
    assert parse('2001-02-03T12:34:56+05:30').start == (
        datetime(2001, 2, 3, 12, 34, 56, 0, tz0530))
    assert parse('2001-02-03T12:34:56-0800').start == (
        datetime(2001, 2, 3, 12, 34, 56, 0, tz08n))


@pytest.mark.skip('Duration not implemented yet')
def test_duration():
    assert parse('2001-02-03T13:00:00/P1Y2M10DT2H30M') == (
        daterange((2001, 2, 3, 13, 0, 0),
                  (2002, 5, 13, 15, 30)))
    assert parse('P1M1D/2001-02-03') == (
        daterange((2001, 1, 31, 13, 0, 0),
                  (2001, 2, 3, 0, 0)))


def test_compare():
    dt = DatetimeRange(datetime(2001, 2, 3, 13),
                       datetime(2001, 2, 3, 15))
    assert (datetime(2001, 2, 3, 12) in dt) is False
    assert (datetime(2001, 2, 3, 13) in dt) is True
    assert (datetime(2001, 2, 3, 14, 23, 59, 59) in dt) is True
    assert (datetime(2001, 2, 3, 15) in dt) is False


def test_compare_with_open_end():
    dt = DatetimeRange(datetime(2001, 2, 3, 13), None)
    assert (datetime(2001, 2, 3, 12) in dt) is False
    assert (datetime(2001, 2, 3, 13) in dt) is True
    assert (datetime(2999, 1, 1) in dt) is True


def test_compare_with_open_start():
    dt = DatetimeRange(None, datetime(2001, 2, 3, 15))
    assert (datetime(2000, 1, 1) in dt) is True
    assert (datetime(2001, 2, 3, 14, 23, 59) in dt) is True
    assert (datetime(2001, 2, 3, 15) in dt) is False
