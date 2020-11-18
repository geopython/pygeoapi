# =================================================================
#
# Authors: Ricardo Garcia Silva <ricardo.garcia.silva@gmail.com>
#
# Copyright (c) 2020 Ricardo Garcia Silva
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

from pygeoapi import starletteutils


@pytest.mark.parametrize('query_params, use_name, expected, expected_list', [
    pytest.param({'foo': 'bar'}, 'foo', 'bar', ['bar'], id='dict-lower-case'),
    pytest.param({'FOO': 'bar'}, 'foo', 'bar', ['bar'], id='dict-upper-case'),
    pytest.param({'Foo': 'bar'}, 'foo', 'bar', ['bar'], id='dict-mixed-case1'),
    pytest.param({'fOO': 'bar'}, 'foo', 'bar', ['bar'], id='dict-mixed-case2'),
    pytest.param('foo=bar', 'foo', 'bar', ['bar'], id='string-lower-case'),
    pytest.param('FOO=bar', 'foo', 'bar', ['bar'], id='string-upper-case'),
    pytest.param('Foo=bar', 'foo', 'bar', ['bar'], id='string-mixed-case'),
    pytest.param('foo=bar&foo=baz', 'foo', 'baz', ['bar', 'baz'], id='string-lower-case-list'),
    pytest.param('FOO=bar&FOO=baz', 'foo', 'baz', ['bar', 'baz'], id='string-upper-case-list'),
    pytest.param('Foo=bar&Foo=baz', 'foo', 'baz', ['bar', 'baz'], id='string-mixed-case-list'),
    pytest.param('foo=bar&FOO=baz', 'foo', 'baz', ['bar', 'baz'], id='string-mixed-case-list2'),
    pytest.param('Foo=bar&fOO=baz', 'foo', 'baz', ['bar', 'baz'], id='string-mixed-case-list3'),
    pytest.param(b'foo=bar', 'foo', 'bar', ['bar'], id='bytes-lower-case'),
    pytest.param(b'FOO=bar', 'foo', 'bar', ['bar'], id='bytes-upper-case'),
    pytest.param(b'Foo=bar', 'foo', 'bar', ['bar'], id='bytes-mixed-case'),
    pytest.param(b'foo=bar&foo=baz', 'foo', 'baz', ['bar', 'baz'], id='bytes-lower-case-list'),
    pytest.param(b'FOO=bar&FOO=baz', 'foo', 'baz', ['bar', 'baz'], id='bytes-upper-case-list'),
    pytest.param(b'Foo=bar&Foo=baz', 'foo', 'baz', ['bar', 'baz'], id='bytes-mixed-case-list'),
    pytest.param(b'foo=bar&FOO=baz', 'foo', 'baz', ['bar', 'baz'], id='bytes-mixed-case-list2'),
    pytest.param(b'Foo=bar&fOO=baz', 'foo', 'baz', ['bar', 'baz'], id='bytes-mixed-case-list3'),
])
def test_pygeoapiqueryparams(query_params, use_name, expected, expected_list):
    data_structure = starletteutils.PygeoapiQueryParams(query_params)
    assert data_structure.get(use_name) == expected
    assert data_structure.getlist(use_name) == expected_list


@pytest.mark.parametrize('key, value', [
    pytest.param('foo', 'bar', marks=pytest.mark.raises(exception=TypeError), id='single-value'),
    pytest.param('foo', ['bar', 'baz'], marks=pytest.mark.raises(exception=TypeError), id='list'),
])
def test_pygeoapiqueryparams_cannot_add_new_keys(key, value):
    data_structure = starletteutils.PygeoapiQueryParams()
    data_structure[key] = value


@pytest.mark.parametrize('existing, key, value', [
    pytest.param(
        starletteutils.PygeoapiQueryParams({'foo': 'bar'}),
        'foo',
        'other',
        marks=pytest.mark.raises(exception=TypeError),
        id='single-value'
    ),
    pytest.param(
        starletteutils.PygeoapiQueryParams({'foo': 'bar'}),
        'foo',
        ['other', 'and another'],
        marks=pytest.mark.raises(exception=TypeError),
        id='list'
    ),
])
def test_pygeoapiqueryparams_cannot_modify_existing_keys(existing, key, value):
    existing[key] = value


@pytest.mark.parametrize('existing, key', [
    pytest.param(
        starletteutils.PygeoapiQueryParams({'foo': 'bar'}),
        'foo',
        marks=pytest.mark.raises(exception=TypeError),
    ),
])
def test_pygeoapiqueryparams_cannot_delete_existing_keys(existing, key):
    del existing[key]
