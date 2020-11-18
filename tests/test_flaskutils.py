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

from pygeoapi import flaskutils

@pytest.mark.parametrize('query_params, use_name, expected, expected_list', [
    pytest.param({'foo': 'bar'}, 'foo', 'bar', ['bar'], id='lower-case'),
    pytest.param({'FOO': 'bar'}, 'foo', 'bar', ['bar'], id='upper-case'),
    pytest.param({'Foo': 'bar'}, 'foo', 'bar', ['bar'], id='mixed-case1'),
    pytest.param({'fOO': 'bar'}, 'foo', 'bar', ['bar'], id='mixed-case2'),
    pytest.param({'foo': ['bar', 'baz']}, 'foo', 'bar', ['bar', 'baz'], id='lower-case-list'),
    pytest.param({'FOO': ['bar', 'baz']}, 'foo', 'bar', ['bar', 'baz'], id='upper-case-list'),
    pytest.param({'Foo': ['bar', 'baz']}, 'foo', 'bar', ['bar', 'baz'], id='mixed-case1-list'),
    pytest.param({'fOO': ['bar', 'baz']}, 'foo', 'bar', ['bar', 'baz'], id='mixed-case2-list'),
])
def test_requestqueryparamsmultidict(query_params, use_name, expected, expected_list):
    data_structure = flaskutils.PygeoapiQueryParamsImmutableMultiDict(query_params)
    assert data_structure.get(use_name) == expected
    assert data_structure.getlist(use_name) == expected_list


@pytest.mark.parametrize('key, value', [
    pytest.param('foo', 'bar', marks=pytest.mark.raises(exception=TypeError), id='single-value'),
    pytest.param('foo', ['bar', 'baz'], marks=pytest.mark.raises(exception=TypeError), id='list'),
])
def test_requestqueryparamsmultidict_cannot_add_new_keys(key, value):
    data_structure = flaskutils.PygeoapiQueryParamsImmutableMultiDict()
    data_structure[key] = value


@pytest.mark.parametrize('existing, key, value', [
    pytest.param(
        flaskutils.PygeoapiQueryParamsImmutableMultiDict({'foo': 'bar'}),
        'foo',
        'other',
        marks=pytest.mark.raises(exception=TypeError),
        id='single-value'
    ),
    pytest.param(
        flaskutils.PygeoapiQueryParamsImmutableMultiDict({'foo': 'bar'}),
        'foo',
        ['other', 'and another'],
        marks=pytest.mark.raises(exception=TypeError),
        id='list'
    ),
])
def test_requestqueryparamsmultidict_cannot_modify_existing_keys(existing, key, value):
    existing[key] = value


@pytest.mark.parametrize('existing, key', [
    pytest.param(
        flaskutils.PygeoapiQueryParamsImmutableMultiDict({'foo': 'bar'}),
        'foo',
        marks=pytest.mark.raises(exception=TypeError),
    ),
])
def test_requestqueryparamsmultidict_cannot_delete_existing_keys(existing, key):
    del existing[key]
