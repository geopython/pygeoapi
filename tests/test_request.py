import pytest

from pygeoapi import flaskutils

@pytest.mark.parametrize('query_params, use_name', [
    pytest.param({'foo': 'bar'}, 'foo', id='lower-case'),
    pytest.param({'FOO': 'bar'}, 'foo', id='upper-case'),
    pytest.param({'Foo': 'bar'}, 'foo', id='mixed-case1'),
    pytest.param({'fOO': 'bar'}, 'foo', id='mixed-case2'),
    pytest.param({'foo': ['bar', 'baz']}, 'foo', id='lower-case-list'),
    pytest.param({'FOO': ['bar', 'baz']}, 'foo', id='upper-case-list'),
    pytest.param({'Foo': ['bar', 'baz']}, 'foo', id='mixed-case1-list'),
    pytest.param({'fOO': ['bar', 'baz']}, 'foo', id='mixed-case2-list'),

])
def test_requestqueryparamsmultidict(query_params, use_name):
    data_structure = flaskutils.RequestQueryParamsImmutableMultiDict(query_params)
    assert data_structure.get(use_name) is not None
    assert data_structure[use_name] is not None
