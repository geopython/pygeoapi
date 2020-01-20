# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
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

from datetime import datetime, date, time
from decimal import Decimal
import os

import pytest

from pygeoapi import util


def get_test_file_path(filename):
    """helper function to open test file safely"""

    if os.path.isfile(filename):
        return filename
    else:
        return 'tests/{}'.format(filename)


def test_get_typed_value():
    value = util.get_typed_value('2')
    assert isinstance(value, int)

    value = util.get_typed_value('1.2')
    assert isinstance(value, float)

    value = util.get_typed_value('1.c2')
    assert isinstance(value, str)


def test_yaml_load():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        d = util.yaml_load(fh)
        assert isinstance(d, dict)
    with pytest.raises(FileNotFoundError):
        with open(get_test_file_path('404.yml')) as fh:
            d = util.yaml_load(fh)


def test_str2bool():
    assert util.str2bool(False) is False
    assert util.str2bool('0') is False
    assert util.str2bool('no') is False
    assert util.str2bool('yes') is True
    assert util.str2bool('1') is True
    assert util.str2bool(True) is True
    assert util.str2bool('true') is True
    assert util.str2bool('True') is True
    assert util.str2bool('TRUE') is True
    assert util.str2bool('tRuE') is True
    assert util.str2bool('on') is True
    assert util.str2bool('On') is True
    assert util.str2bool('off') is False


def test_json_serial():
    d = datetime(1972, 10, 30)
    assert util.json_serial(d) == '1972-10-30T00:00:00'

    d = date(2010, 7, 31)
    assert util.json_serial(d) == '2010-07-31'

    d = time(11)
    assert util.json_serial(d) == '11:00:00'

    d = Decimal(1.0)
    assert util.json_serial(d) == 1.0

    with pytest.raises(TypeError):
        util.json_serial('foo')


def test_mimetype():
    assert util.get_mimetype('file.xml') == 'application/xml'
    assert util.get_mimetype('file.yml') == 'text/plain'
    assert util.get_mimetype('file.yaml') == 'text/plain'
