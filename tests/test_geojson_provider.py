# =================================================================
#
# Authors: Matthew Perry <perrygeo@gmail.com>
#
# Copyright (c) 2018 Matthew Perry
# Copyright (c) 2019 Tom Kralidis
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

import json
import os
import logging
import pytest

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.geojson import GeoJSONProvider

LOGGER = logging.getLogger(__name__)

path = '/tmp/test.geojson'


@pytest.fixture()
def fixture():
    data = {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'id': '123-456',
            'geometry': {
                'type': 'Point',
                'coordinates': [125.6, 10.1]},
            'properties': {
                'name': 'Dinagat Islands'}}]}

    with open(path, 'w') as fh:
        fh.write(json.dumps(data))
    return path


@pytest.fixture()
def config():
    return {
        'name': 'GeoJSON',
        'type': 'feature',
        'data': path,
        'id_field': 'id'
    }


def test_query(fixture, config):
    p = GeoJSONProvider(config)

    fields = p.get_fields()
    assert len(fields) == 1
    assert fields['name'] == 'string'

    results = p.query()
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1
    assert results['features'][0]['id'] == '123-456'


def test_get(fixture, config):
    p = GeoJSONProvider(config)
    results = p.get('123-456')
    assert isinstance(results, dict)
    assert 'Dinagat' in results['properties']['name']


def test_get_not_existing_item_raise_exception(
    fixture, config
):
    """Testing query for a not existing object"""
    p = GeoJSONProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_delete(fixture, config):
    p = GeoJSONProvider(config)
    p.delete('123-456')

    results = p.query()
    assert len(results['features']) == 0


def test_create(fixture, config):
    p = GeoJSONProvider(config)
    new_feature = {
        'type': 'Feature',
        'id': '123-456',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]},
        'properties': {
            'name': 'Null Island'}}

    p.create(new_feature)

    results = p._load()
    assert len(results['features']) == 2
    assert 'Dinagat' in results['features'][0]['properties']['name']
    assert 'Null' in results['features'][1]['properties']['name']


def test_update(fixture, config):
    p = GeoJSONProvider(config)
    new_feature = {
        'type': 'Feature',
        'id': '123-456',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]},
        'properties': {
            'name': 'Null Island'}}

    p.update('123-456', new_feature)

    # Should be changed
    results = p.get('123-456')
    assert 'Null' in results['properties']['name']


"""
    def __init__(self, definition):
        BaseProvider.__init__(self, definition)
    def _load(self):
    def query(self):
    def get(self, identifier):
    def create(self, new_feature):
    def update(self, identifier, new_feature):
    def delete(self, identifier):
    def __repr__(self):
"""


def get_cql_test_file_path(filename):
    """helper function to open test file safely"""

    if os.path.isfile(filename):
        return filename
    else:
        return 'tests/{}'.format(filename)


cql_path = get_cql_test_file_path('data/ne_110m_lakes.geojson')


@pytest.fixture()
def cql_config():
    return {
        'name': 'GeoJSON',
        'data': cql_path,
        'id_field': 'id'
    }


# test on common comparisons operations
def test_cql_eq(cql_config):
    """Testing query for equals `=` CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='id = 24')
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1
    results = p.query(cql_expression='name="Lake Baikal"')
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1


def test_cql_ne(cql_config):
    """Testing query for not-equals `<>`  CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='id <> 24')
    # assert considering the limit as 10
    assert len(results['features']) == 10
    assert results['numberMatched'] == 24
    assert results['numberReturned'] == 10


def test_cql_lt(cql_config):
    """Testing query for less-than `<` CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='id < 10')
    assert len(results['features']) == 10
    assert results['numberMatched'] == 10
    assert results['numberReturned'] == 10


def test_cql_le(cql_config):
    """Testing query for less-than-equals-to `<=` CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='id <= 10')
    # assert considering the limit as 10
    assert len(results['features']) == 10
    assert results['numberMatched'] == 11
    assert results['numberReturned'] == 10


def test_cql_gt(cql_config):
    """Testing query for greater-than `>` CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='id > 23')
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1


def test_cql_ge(cql_config):
    """Testing query for greater-than-equals-to `>=` CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='id >= 24')
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1


def test_cql_not(cql_config):
    """Testing query for `not` CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='NOT id >= 24')
    assert len(results['features']) == 10
    assert results['numberMatched'] == 24
    assert results['numberReturned'] == 10


# test on logical operators
def test_cql_and(cql_config):
    """Testing query for multiple sub-filters combined by `AND`
    in CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='id<5 AND name LIKE "Lake%"')
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2


def test_cql_or(cql_config):
    """Testing query for multiple sub-filters combined by `OR`
    in CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='id<5 OR name LIKE "%Lake"')
    assert len(results['features']) == 8
    assert results['numberMatched'] == 8
    assert results['numberReturned'] == 8


def test_cql_and_or(cql_config):
    """Testing query for multiple sub-filters combined by `AND` and `OR`
    in CQL filter expression """

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='id<5 OR id>5 AND name LIKE "%Baikal"')
    assert len(results['features']) == 5
    assert results['numberMatched'] == 5
    assert results['numberReturned'] == 5


def test_cql_and_and(cql_config):
    """Testing query for multiple sub-filters combined by multiple `AND`
    in CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='id<5 AND name LIKE "%Baikal" '
                                     'AND type LIKE "Feature"')
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1


def test_cql_between(cql_config):
    """Testing query for between in CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    # inclusive of low and high values
    results = p.query(cql_expression='id BETWEEN 2 AND 5')
    assert len(results['features']) == 4
    assert results['numberMatched'] == 4
    assert results['numberReturned'] == 4


def test_cql_not_between(cql_config):
    """Testing query for between in CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    # inclusive of low and high values
    results = p.query(cql_expression='id NOT BETWEEN 10 AND 20')
    assert len(results['features']) == 10
    assert results['numberMatched'] == 14
    assert results['numberReturned'] == 10


def test_cql_is_null(cql_config):
    """Testing query for null in CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='admin IS NULL')
    assert len(results['features']) == 10
    assert results['numberMatched'] == 17
    assert results['numberReturned'] == 10


def test_cql_is_not_null(cql_config):
    """Testing query for not null in CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    # inclusive of low and high values
    results = p.query(cql_expression='admin IS NOT NULL')
    assert len(results['features']) == 8
    assert results['numberMatched'] == 8
    assert results['numberReturned'] == 8


def test_cql_in(cql_config):
    """Testing query for IN CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    # inclusive of low and high values
    results = p.query(
        cql_expression="name IN ('Lake Baikal','Lake Huron',"
                       "'Lake Onega','Lake Victoria')"
    )
    assert len(results['features']) == 4
    assert results['numberMatched'] == 4
    assert results['numberReturned'] == 4


# test on NOT IN operation
def test_cql_not_in(cql_config):
    """Testing query for IN CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    # inclusive of low and high values
    results = p.query(
        cql_expression="name NOT IN ('Lake Baikal','Lake Huron',"
                       "'Lake Onega','Lake Victoria')"
    )
    assert len(results['features']) == 10
    assert results['numberMatched'] == 21
    assert results['numberReturned'] == 10


# test with limit, startindex and CQL filter
def test_cql_limit_filter(cql_config):
    """Testing query for filter, startindex and CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(limit=9, startindex=5, cql_expression='id>10')
    assert len(results['features']) == 9
    assert results['numberMatched'] == 14
    assert results['numberReturned'] == 9


# test on LIKE operation
def test_cql_like(cql_config):
    """Testing query for filter, startindex and CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='name LIKE "%Lake%"')
    assert len(results['features']) == 10
    assert results['numberMatched'] == 18
    assert results['numberReturned'] == 10
    results = p.query(cql_expression='name ILIKE "%Lake%"')
    assert len(results['features']) == 10
    assert results['numberMatched'] == 18
    assert results['numberReturned'] == 10


# test on LIKE operation
def test_cql_not_like(cql_config):
    """Testing query for filter, startindex and CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='name NOT LIKE "%Lake%"')
    assert len(results['features']) == 7
    assert results['numberMatched'] == 7
    assert results['numberReturned'] == 7


# test on spatial operation
def test_cql_spatial(cql_config):
    """Testing query for filter, startindex and CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(cql_expression='INTERSECTS(geometry,POINT(105 52))')
    assert len(results['features']) == 0
    assert results['numberMatched'] == 0
    assert results['numberReturned'] == 0
    results = p.query(
        cql_expression='CONTAINS(geometry,'
                       'POLYGON((108.58 54.19, 108.37 54.04, '
                       '108.48 53.94, 108.77 54.01, 108.77 54.11, '
                       '108.58 54.19)))')
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1
    results = p.query(
        cql_expression='WITHIN(geometry,'
                       'POLYGON((-112.32 49.83, -94.21 49.83, '
                       '-94.21 59.97, -112.32 59.97, -112.32 49.83)))'
    )
    assert len(results['features']) == 4
    assert results['numberMatched'] == 4
    assert results['numberReturned'] == 4
    results = p.query(
        cql_expression='TOUCHES(geometry,'
                       'LINESTRING(-84.8642248660326 47.8600843833932, '
                       '-84.8641987144947 47.86004276738763))'
    )
    assert len(results['features']) == 0
    assert results['numberMatched'] == 0
    assert results['numberReturned'] == 0
    results = p.query(cql_expression='DISJOINT(geometry,POINT(-81.95 44.93))')
    assert len(results['features']) == 10
    assert results['numberMatched'] == 24
    assert results['numberReturned'] == 10
    results = p.query(
        cql_expression='EQUALS(geometry,'
                       'POLYGON((-101.89514441608819 58.01403025983099, '
                       '-102.12874772826359 58.01914622662788, '
                       '-102.81369300007623 57.46434804954232, '
                       '-102.81322791218561 57.28714956321349, '
                       '-102.57680823445028 56.938281968811054, '
                       '-103.01440426309787 56.56510061301529, '
                       '-103.07832800984292 56.71080231386223, '
                       '-103.1487371488406 56.70411021588043, '
                       '-103.2825015938281 56.40994212505895, '
                       '-103.20416012247362 56.34539826112639, '
                       '-101.93403093138781 57.23066722271848, '
                       '-101.97090206582807 57.34867035585697, '
                       '-101.54384802936804 57.86809601503873, '
                       '-101.89514441608819 58.01403025983099, '
                       '-101.89514441608819 58.01403025983099)))'
    )

    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1
    results = p.query(
        cql_expression='OVERLAPS(geometry,'
                       'POLYGON((-80.09 43.65, -80.36 43.25, '
                       '-80.12 42.96, -79.19 42.41, -78.53 43.11,'
                       ' -79.23 43.54, -80.09 43.65)))'
    )
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2
    results = p.query(
        cql_expression='CROSSES(geometry,'
                       'LINESTRING(-84.86427616328001 47.86009630581028, '
                       '-84.86421380192041 47.86002792058838))'
    )
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1
    results = p.query(
        cql_expression='BEYOND(geometry,POINT(-85 75),10000,meters)'
    )
    assert len(results['features']) == 10
    assert results['numberMatched'] == 25
    assert results['numberReturned'] == 10
    results = p.query(
        cql_expression='DWITHIN(geometry,POINT(-85 75),10,kilometers)'
    )
    assert len(results['features']) == 0
    assert results['numberMatched'] == 0
    assert results['numberReturned'] == 0
    results = p.query(
        cql_expression='RELATE(geometry,POINT (-85 75), "T*****FF*")'
    )
    assert len(results['features']) == 0
    assert results['numberMatched'] == 0
    assert results['numberReturned'] == 0
    results = p.query(cql_expression='BBOX(geometry, -90, 40, -60, 45)')
    assert len(results['features']) == 4
    assert results['numberMatched'] == 4
    assert results['numberReturned'] == 4


def test_cql_hits(cql_config):
    """Testing result type hits for spatial CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    results = p.query(
        resulttype='hits',
        cql_expression='WITHIN(geometry,'
                       'POLYGON((-112.32 49.83, -94.21 49.83, '
                       '-94.21 59.97, -112.32 59.97, '
                       '-112.32 49.83))) AND id>=20'
    )
    assert len(results['features']) == 0
    assert results['numberMatched'] == 2
    results = p.query(resulttype='hits', cql_expression='name LIKE "%Lake%"')
    assert len(results['features']) == 0
    assert results['numberMatched'] == 18


def test_cql_auxiliary_expressions(cql_config):
    """Testing for incorrect CQL filter expression"""

    p = GeoJSONProvider(cql_config)
    try:
        results = p.query(cql_expression="name>'Lake Baikal'")
        assert results.get('features', None) is None
        results = p.query(cql_expression="name@'lake'")
        assert results.get('features', None) is None
        results = p.query(cql_expression='JOINS(geometry,POINT(105 52))')
        assert results.get('features', None) is None
        results = p.query(cql_expression='INTERSECTS(shape,POINT(105 52))')
        assert results.get('features', None) is None
        results = p.query(
            cql_expression='datetime FOLLOWING 2001-10-30T14:24:55Z'
        )
        assert results.get('features', None) is None
        results = p.query(cql_expression='name LIKE 2')
        assert results.get('features', None) is None
        results = p.query(cql_expression='id BETWEEN 2 AND "A"')
        assert results.get('features', None) is None
        results = p.query(cql_expression='id IS NULLS')
        assert results.get('features', None) is None
        results = p.query(cql_expression='id IN ["A","B"]')
        assert results.get('features', None) is None

    except Exception as err:
        LOGGER.error(err)
