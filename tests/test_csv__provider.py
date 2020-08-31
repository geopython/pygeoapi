# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2018 Tom Kralidis
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

import os
import logging
import pytest

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.csv_ import CSVProvider


def get_test_file_path(filename):
    """helper function to open test file safely"""

    if os.path.isfile(filename):
        return filename
    else:
        return 'tests/{}'.format(filename)


LOGGER = logging.getLogger(__name__)


path = get_test_file_path('data/obs.csv')


@pytest.fixture()
def config():
    """function to return file configuration object"""

    return {
        'name': 'CSV',
        'data': path,
        'id_field': 'id',
        'geometry': {
            'x_field': 'long',
            'y_field': 'lat'
        }
    }


def test_query(config):
    """Testing query method"""

    p = CSVProvider(config)

    fields = p.get_fields()
    assert len(fields) == 6
    assert fields['value'] == 'string'
    assert fields['stn_id'] == 'string'

    results = p.query()
    assert len(results['features']) == 5
    assert results['numberMatched'] == 5
    assert results['numberReturned'] == 5
    assert results['features'][0]['id'] == '371'
    assert results['features'][0]['properties']['value'] == '89.9'

    assert results['features'][0]['geometry']['coordinates'][0] == -75.0
    assert results['features'][0]['geometry']['coordinates'][1] == 45.0

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '371'

    results = p.query(startindex=2, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '238'

    assert len(results['features'][0]['properties']) == 3

    config['properties'] = ['value', 'stn_id']
    p = CSVProvider(config)
    results = p.query()
    assert len(results['features'][0]['properties']) == 2


def test_get(config):
    """Testing get method"""

    p = CSVProvider(config)
    result = p.get('964')
    assert result['id'] == '964'
    assert result['properties']['value'] == '99.9'


def test_get_not_existing_item_raise_exception(config):
    """Testing query for a not existing object"""

    p = CSVProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get('404')


# test on common comparisons operations
def test_cql_eq(config):
    """Testing query for equals `=` CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='id = 377')
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1


def test_cql_ne(config):
    """Testing query for not-equals `<>`  CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='id <> 355')
    assert len(results['features']) == 5
    assert results['numberMatched'] == 5
    assert results['numberReturned'] == 5


def test_cql_lt(config):
    """Testing query for less-than `<` CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='stn_id < 604')
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2


def test_cql_le(config):
    """Testing query for less-than-equals-to `<=` CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='stn_id <= 604')
    assert len(results['features']) == 3
    assert results['numberMatched'] == 3
    assert results['numberReturned'] == 3


def test_cql_gt(config):
    """Testing query for greater-than `>` CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='id > 964')
    assert len(results['features']) == 0
    assert results['numberMatched'] == 0
    assert results['numberReturned'] == 0


def test_cql_ge(config):
    """Testing query for greater-than-equals-to `>=` CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='id >= 964')
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1


def test_cql_not(config):
    """Testing query for `not` filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='NOT id >= 964')
    assert len(results['features']) == 4
    assert results['numberMatched'] == 4
    assert results['numberReturned'] == 4


# test on logical operators
def test_cql_and(config):
    """Testing query for multiple sub-filters combined by `AND`
    in CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='stn_id < 2147 AND id > 377')
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1


def test_cql_or(config):
    """Testing query for multiple sub-filters combined by `OR`
    in CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='stn_id < 2147 OR id > 377')
    assert len(results['features']) == 3
    assert results['numberMatched'] == 3
    assert results['numberReturned'] == 3


def test_cql_and_or(config):
    """Testing query for multiple sub-filters combined by `AND` and `OR`
    in CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='stn_id <> 35 AND id >= 238 OR id <= 964') # noqa
    assert len(results['features']) == 3
    assert results['numberMatched'] == 3
    assert results['numberReturned'] == 3


def test_cql_and_and(config):
    """Testing query for multiple sub-filters combined by multiple `AND`
    in CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='stn_id <> 35 AND id > 238 AND id < 964') # noqa
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1


# test on BETWEEN operation
def test_cql_between(config):
    """Testing query for between CQL filter expression"""

    p = CSVProvider(config)
    # inclusive of low and high values
    results = p.query(cql_expression='id BETWEEN 355 AND 500')
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2


# test on NOT BETWEEN operation
def test_cql_not_between(config):
    """Testing query for not between CQL filter expression"""

    p = CSVProvider(config)
    # inclusive of low and high values
    results = p.query(cql_expression='id NOT BETWEEN 200 AND 300')
    assert len(results['features']) == 3
    assert results['numberMatched'] == 3
    assert results['numberReturned'] == 3


# test on IS NULL operation
def test_cql_is_null(config):
    """Testing query for null CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='id IS NULL')
    assert len(results['features']) == 0
    assert results['numberMatched'] == 0
    assert results['numberReturned'] == 0


# test on IS NOT NULL operation
def test_cql_is_not_null(config):
    """Testing query for not null CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(cql_expression='id IS NOT NULL')
    assert len(results['features']) == 5
    assert results['numberMatched'] == 5
    assert results['numberReturned'] == 5


# test on IN operation
def test_cql_in(config):
    """Testing query for IN CQL filter expression"""

    p = CSVProvider(config)
    # inclusive of low and high values
    results = p.query(cql_expression="id IN ('377','297')")
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2


# test on NOT IN operation
def test_cql_not_in(config):
    """Testing query for not IN CQL filter expression"""

    p = CSVProvider(config)
    # inclusive of low and high values
    results = p.query(cql_expression="id NOT IN ('377','297')")
    assert len(results['features']) == 3
    assert results['numberMatched'] == 3
    assert results['numberReturned'] == 3


# test with limit, startindex and CQL filter
def test_cql_limit_filter(config):
    """Testing query for filter, startindex and CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(limit=5, startindex=3, cql_expression='id>100')
    assert len(results['features']) == 2
    assert results['numberMatched'] == 5
    assert results['numberReturned'] == 2


# test on LIKE operation
def test_cql_like(config):
    """Testing query for filter, startindex and CQL filter expression"""

    pass


# test on LIKE operation
def test_cql_not_like(config):
    """Testing query for filter, startindex and CQL filter expression"""

    pass


# test on spatial operation
def test_cql_spatial(config):
    """Testing query for spatial CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(
        cql_expression='INTERSECTS(geometry,POINT (-75 45))'
    )
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2
    results = p.query(
        cql_expression='CONTAINS(geometry,'
                       'POLYGON((-80.0 -80.0,-80.0 50,80.0 50,-80.0 -80.0)))'
    )
    assert len(results['features']) == 0
    assert results['numberMatched'] == 0
    assert results['numberReturned'] == 0
    results = p.query(
        cql_expression='WITHIN(geometry,'
                       'POLYGON((-80.0 -80.0,-80.0 50,80.0 50,-80.0 -80.0)))'
    )
    assert len(results['features']) == 4
    assert results['numberMatched'] == 4
    assert results['numberReturned'] == 4
    results = p.query(
        cql_expression='TOUCHES(geometry,LINESTRING(-75 45, -10 10))'
    )
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2
    results = p.query(
        cql_expression='DISJOINT(geometry,POINT (-75 45))'
    )
    assert len(results['features']) == 3
    assert results['numberMatched'] == 3
    assert results['numberReturned'] == 3
    results = p.query(
        cql_expression='EQUALS(geometry,POINT (-75 45))'
    )
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2
    results = p.query(
        cql_expression='OVERLAPS(geometry,POINT (-74 45))'
    )
    assert len(results['features']) == 0
    assert results['numberMatched'] == 0
    assert results['numberReturned'] == 0
    results = p.query(
        cql_expression='CROSSES(geometry,LINESTRING(-75 45, -10 10))'
    )
    assert len(results['features']) == 0
    assert results['numberMatched'] == 0
    assert results['numberReturned'] == 0
    results = p.query(
        cql_expression='BEYOND(geometry,POINT(-65 45),10000,meters)'
    )
    assert len(results['features']) == 3
    assert results['numberMatched'] == 3
    assert results['numberReturned'] == 3
    results = p.query(
        cql_expression='DWITHIN(geometry,POINT(-65 45),10,kilometers)'
    )
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2
    results = p.query(
        cql_expression='RELATE(geometry,POINT (-75 45), "T*****FF*")'
    )
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2
    results = p.query(cql_expression='BBOX(geometry, -90, 40, -60, 45)')
    assert len(results['features']) == 4
    assert results['numberMatched'] == 4
    assert results['numberReturned'] == 4


# test on temporal operation
def test_cql_temporal(config):
    """Testing query for spatial CQL filter expression"""

    p = CSVProvider(config)

    results = p.query(
        cql_expression='datetime BEFORE 2001-10-30T14:24:55Z'
    )
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2
    results = p.query(
        cql_expression='datetime BEFORE OR DURING '
                       '2003-01-01T00:00:00Z/2005-01-01T00:00:00Z'
    )
    assert len(results['features']) == 4
    assert results['numberMatched'] == 4
    assert results['numberReturned'] == 4
    results = p.query(
        cql_expression='datetime DURING '
                       '2003-01-01T00:00:00Z/2005-01-01T00:00:00Z'
    )
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1
    results = p.query(
        cql_expression='datetime DURING OR AFTER '
                       '2003-01-01T00:00:00Z/2005-01-01T00:00:00Z'
    )
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2
    results = p.query(
        cql_expression='datetime AFTER 2001-10-30T14:24:55Z'
    )
    assert len(results['features']) == 4
    assert results['numberMatched'] == 4
    assert results['numberReturned'] == 4


def test_cql_hits(config):
    """Testing result type hits for spatial CQL filter expression"""

    p = CSVProvider(config)
    results = p.query(
        resulttype='hits',
        cql_expression='WITHIN(geometry,'
                       'POLYGON((-80.0 -80.0,-80.0 50,'
                       '80.0 50,-80.0 -80.0))) AND id<>371'
    )
    assert results['numberMatched'] == 3


def test_cql_auxiliary_expressions(config):
    """Testing for incorrect CQL filter expression"""

    p = CSVProvider(config)
    try:
        results = p.query(cql_expression="id>'A'")
        assert results.get('features', None) is None
        results = p.query(cql_expression="name@'obs'")
        assert results.get('features', None) is None
        results = p.query(cql_expression='JOINS(geometry,POINT(105 52))')
        assert results.get('features', None) is None
        results = p.query(cql_expression='INTERSECTS(shape,POINT(105 52))')
        assert results.get('features', None) is None
        results = p.query(
            cql_expression='datetime FOLLOWING 2001-10-30T14:24:55Z'
        )
        assert results.get('features', None) is None
        results = p.query(cql_expression='  ')
        assert results.get('features', None) is None
        results = p.query(cql_expression='id BETWEEN 2 AND "A"')
        assert results.get('features', None) is None
        results = p.query(cql_expression='id IS NULLS')
        assert results.get('features', None) is None
        results = p.query(cql_expression='id IN ["A","B"]')
        assert results.get('features', None) is None
    except Exception as err:
        LOGGER.error(err)
