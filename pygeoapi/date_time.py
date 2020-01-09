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

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

LOGGER = logging.getLogger(__name__)

TIME_RE = re.compile(r'^(\d\d)?:?(\d\d)?:?(\d\d)?(?:[\.,](\d+))?'
                     r'(Z|[+-]\d\d:?(?:\d\d)?)?$')
DATE_RE = re.compile(r'^(\d\d\d\d)-?(\d\d)?-?(\d\d)?$')
# match before 'T'
DATE_BW = re.compile(r'^(?:(?:(?:(\d\d\d\d)-?)?(\d\d)-?)?(\d\d))?$')
TIMEZONE_RE = re.compile(r'^([+-])(\d\d):?(\d\d)?$')


class DatetimeRange(object):
    '''
    DatetimeRange contains date range with
    start (inclusive)
    end (exclusive)
    datetimes.
    E.g. 2007-03-01 will contain:
    start = 2007-03-01
    end = 2007-03-02
    '''

    def __init__(self, start: Optional[datetime], end: Optional[datetime]):
        """
        constructor

        :param start: beginning of the range (inclusive)
        :param end: end of the range (exclusive)

        :returns: `pygeoapi.DatetimeRange` instance
        """
        self.start = start
        self.end = end

    def __tuple__(self):
        """
        Get start, end as a tuple

        :returns: tuple of (start, end)
        """
        return (self.start, self.end)

    def __contains__(self, other: datetime):
        """
        Check if given date is within date range of
        self.begin <= checked datetime < self.end

        :param other: datetime that will be checked

        :returns: true, if other is inside the date range, othewise false
        """
        if self.start and self.end:
            return self.start <= other < self.end
        if self.start and self.end is None:
            return self.start <= other
        elif self.start is None and self.end:
            return other < self.end

    def __eq__(self, other):
        """
        Equals

        :param other: DatetimeRange that will be checked

        :returns: true, if other is identical to self
        """
        if not isinstance(other, DatetimeRange):
            return NotImplemented
        return (self.start, self.end) == (other.start, other.end)

    def __repr__(self):
        """
        String representation

        :returns: string representation of DatetimeRange
        """
        start = self.start.isoformat() if (self.start is not None) else '..'
        end = self.end.isoformat() if (self.end is not None) else '..'
        return 'DatetimeRange({}/{})'.format(start, end)


def parse(s: str) -> DatetimeRange:
    '''Parse ISO8601 / RFC 3339 string to DatetimeRange

    :param s: String to be parsed

    :returns: DatetimeRange instance
    E.g.
        s='2007-03-01'
            (start = 2007-03-01T00:00:00, end = 2007-03-02T00:00:00)
        s='2007-03-01T12'
            (start = 2007-03-01T12:00:00, end = 2007-03-01T13:00:00)
        s='2007-03-01T13:00:00/2008-05-11T15:30:00'
            (start = 2007-03-01T13:00:00, end = 2008-05-11T15:30:00)
        s='2007-03-01T13:00:00/2007-04-01'
            (start = 2007-03-01T13:00:00, end = 2007-04-02T00:00)
        s='2007-03-01T13:00:00/15:00'
            (start = 2007-03-01T13:00:00, end = 2007-03-01T15:01)
        s='2007-03-01T13:30:00/02T16'
            (start = 2007-03-01T13:30:00, end = 2007-03-02T17:00)
        s='2007-03-01T13:00:00/T24'
            (start = 2007-03-01T13:00:00, end = 2007-03-02T00:00)
        s='2007-03-01T13:00:00/..'
            (start = 2007-03-01T13:00:00, end = None)
        s='../2007-03-01T13:00:00'
            (start = None, end = 2007-03-01T13:00:00)
    '''
    LOGGER.debug('Parsing datetime range from: ' + s)
    first, sep, second = s.partition('/')
    if sep:
        start = parse_datetime(first)
        end = parse_datetime(second)
    else:
        start = end = parse_datetime(first)

    if start and end:
        start = complete(start, end)
        end = complete(end, start)

    d_start = to_datetime(start) if start else None
    d_end = to_datetime(end, ceil=True) if end else None

    return DatetimeRange(d_start, d_end)


def prefer(a, b):
    """
    Prefer value, which is not None

    :param a: First value
    :param b: Second value

    :returns: a if it is not None, othewise b
    """
    return a if (a is not None) else b


def int_or_none(a):
    """
    Try to convert to int

    :param a: Value to be converted

    :returns: int if not None, throws if not convertible to int
    """
    return int(a) if (a is not None) else None


def match(regexp, s: str) -> Tuple[str]:
    """
    Try to match given string with given regexp

    :param regexp: Regexp to be used
    :param s: string to be regexped

    :returns: tuple of matched strings
    """
    m = regexp.match(s)
    if m is None:
        raise ValueError('Invalid datetime string: {}'.format(s))
    return m.groups()


def parse_timezone(s: str):
    """
    Find timezone info from string

    :param s: String containing timezone info

    :returns: Instance of datetime.timezone.
    If no timezone in string, None returned
    """
    if s is None:
        return None
    elif s == 'Z':
        return timezone.utc
    else:
        sign, hours, minutes = match(TIMEZONE_RE, s)
        delta = timedelta(hours=int(hours), minutes=int_or_none(minutes) or 0)
        return timezone(delta if (sign == '+') else -delta)


def date_tuple(year, month, day) -> Tuple[Optional[int]]:
    """
    Get tuple of given parameters

    :param year: Year as str (or None)
    :param month: Month as str (or None)
    :param day: Day as str (or None)

    :returns: tuple of (year, month, date) that can contain None's
    """
    return int_or_none(year), int_or_none(month), int_or_none(day)


def time_tuple(hour, minute, second, fraction, tz) -> tuple:
    """
    Get tuple of given parameters

    :param hour: Hour as str (or None)
    :param minute: Minute as str (or None)
    :param second: Second as str (or None)
    :param fraction: fraction of the second as str (or None)
    :param tz: Timezone as str (or None)

    :returns: tuple of
    (hour, minute, second, microsecond, precision, timezone),
    that can contain None's. Precision defines the precision
    of microseconds
    """
    precision = len(fraction[:6]) if fraction else None
    microsecond = fraction[:6].ljust(6, '0') if fraction else None
    return (int_or_none(hour), int_or_none(minute), int_or_none(second),
            int_or_none(microsecond), precision, parse_timezone(tz))


def parse_datetime(s: str) -> Optional[tuple]:
    """
    Parse datetime string

    :param s: String to be parsed

    :returns: tuple of (year, month, date, hour, minute, second, microsecond,
    precision, timezone), where precision defines the precision
    of microseconds
    """
    LOGGER.debug('Parsing datetime from: ' + s)
    if s == '..':
        return None

    if 'T' in s:
        s1, _, s2 = s.partition('T')
        date = date_tuple(*match(DATE_BW, s1))
        time = time_tuple(*match(TIME_RE, s2))
    else:
        if ':' in s:
            time = time_tuple(*match(TIME_RE, s))
            date = (None, None, None)
        else:
            date = date_tuple(*match(DATE_RE, s))
            time = (None, None, None, None, None, None)

    return date + time


def complete(d0: tuple, d1: tuple) -> tuple:
    """
    Replace leading None values of d0 by corresponding value of d1
    E.g. d0=(None, None, 21, 10, None, 24 ...)
         d1=(2020, 1, 22, 11, 17, 21 ...)
    will lead to (2020, 1, 21, 10, None, 24 ...)

    :param d0: tuple, containing date and time as separate values
    :param d1: tuple, containing date and time as separate values

    :returns: tuple, containing date and time as separate values
    """
    leading_nones = next(i for i, v in enumerate(d0) if v is not None)
    return d1[:leading_nones] + d0[leading_nones:]


def to_datetime(values: tuple, ceil=False) -> datetime:
    """
    Convert tuple to datetime.
    Replace None values by 0 (in case of day/month by 1).

    :param values: tuple, containing date and time. See: parse_datetime()
    :param ceil: In case of ceil=True:
    increment last not None field by one (excluded end time).

    :returns Instance of datetime
    """
    (year, month, day, hour, minute,
     second, microsecond, digits, tzinfo) = values

    if ceil:  # round end time up
        if (hour == 24 and minute in (None, 0) and second in (None, 0)
                and microsecond in (None, 0)):
            # special case 24[:00:00.000]
            # means beginning of the next day (exclusive)
            hour = minute = second = microsecond = 0
            day += 1
        elif microsecond is not None:
            microsecond += 10 ** (6-digits)
        elif microsecond is None and second is not None:
            second += 1
        elif second is None and minute is not None:
            minute += 1
        elif minute is None and hour is not None:
            hour += 1
        elif hour is None and day is not None:
            day += 1
        elif day is None and month is not None:
            month += 1
        elif month is None:
            year += 1

    month = month or 1

    if month > 12:
        year, month = year + (month // 12), ((month - 1) % 12) + 1

    return datetime(year, month, 1, tzinfo=tzinfo) + timedelta(
                    days=(day or 1) - 1,
                    hours=hour or 0,
                    minutes=minute or 0,
                    seconds=second or 0,
                    microseconds=microsecond or 0)
