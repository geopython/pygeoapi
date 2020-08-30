# =================================================================
#
# Authors: Just van den Broecke <justb4@gmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2019 Just van den Broecke
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

# Needs to be run like: python3 -m pytest

import pytest
import logging

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.postgresql import PostgreSQLProvider

LOGGER = logging.getLogger(__name__)


@pytest.fixture()
def config():
    return {
        'name': 'PostgreSQL',
        'data': {'host': '127.0.0.1',
                 'dbname': 'test',
                 'user': 'postgres',
                 'password': 'postgres',
                 'search_path': ['osm', 'public']
                 },
        'id_field': 'osm_id',
        'table': 'hotosm_bdi_waterways',
        'geom_field': 'foo_geom'
    }


def test_query(config):
    """Testing query for a valid JSON object with geometry"""

    p = PostgreSQLProvider(config)
    feature_collection = p.query()
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert features is not None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    geometry = feature.get('geometry', None)
    assert geometry is not None


def test_query_with_property_filter(config):
    """Test query  valid features when filtering by property"""
    p = PostgreSQLProvider(config)
    feature_collection = p.query(properties=[("waterway", "stream")])
    features = feature_collection.get('features', None)
    stream_features = list(
        filter(lambda feature: feature['properties']['waterway'] == 'stream',
               features))
    assert (len(features) == len(stream_features))

    feature_collection = p.query()
    features = feature_collection.get('features', None)
    stream_features = list(
        filter(lambda feature: feature['properties']['waterway'] == 'stream',
               features))
    other_features = list(
        filter(lambda feature: feature['properties']['waterway'] != 'stream',
               features))
    # assert (len(features) != len(stream_features))
    # assert (len(other_features) != 0)


def test_query_hits(config):
    """Test query resulttype=hits with properties"""
    psp = PostgreSQLProvider(config)
    results = psp.query(resulttype="hits")
    assert results["numberMatched"] == 14776

    results = psp.query(
        bbox=[29.3373, -3.4099, 29.3761, -3.3924], resulttype="hits")
    assert results["numberMatched"] == 5

    results = psp.query(properties=[("waterway", "stream")], resulttype="hits")
    assert results["numberMatched"] == 13930


def test_query_bbox(config):
    """Test query with a specified bounding box"""
    psp = PostgreSQLProvider(config)
    boxed_feature_collection = psp.query(
        bbox=[29.3373, -3.4099, 29.3761, -3.3924]
    )
    assert len(boxed_feature_collection['features']) == 5


def test_get(config):
    """Testing query for a specific object"""
    p = PostgreSQLProvider(config)
    result = p.get(29701937)
    assert isinstance(result, dict)
    assert 'geometry' in result
    assert 'properties' in result
    assert 'id' in result
    assert 'Kanyosha' in result['properties']['name']


def test_get_not_existing_item_raise_exception(config):
    """Testing query for a not existing object"""
    p = PostgreSQLProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_cql_query(config):
    """Testing cql query for a valid JSON object with geometry for sqlite3"""

    p = PostgreSQLProvider(config)
    feature_collection = p.query(
        cql_expression='waterway = "stream"', limit=20)
    features = feature_collection.get('features', None)
    assert len(features) == 20
    feature_collection = p.query(
        cql_expression='depth = "10"', limit=20)
    features = feature_collection.get('features', None)
    assert len(features) == 4
    feature_collection = p.query(
        cql_expression='width IS NOT NULL', limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 119
    feature_collection = p.query(
        cql_expression='width IS NULL', limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 200
    feature_collection = p.query(
        cql_expression='osm_id < 3000', limit=20)
    features = feature_collection.get('features', None)
    assert len(features) == 0
    feature_collection = p.query(
        cql_expression='osm_id <= 3000', limit=20)
    features = feature_collection.get('features', None)
    assert len(features) == 0
    feature_collection = p.query(
        cql_expression='osm_id > 4000', limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 200
    feature_collection = p.query(
        cql_expression='osm_id >= 4000', limit=20000)
    features = feature_collection.get('features', None)
    assert len(features) == 14776
    feature_collection = p.query(
        cql_expression='waterway LIKE "d%"',
        limit=500)
    features = feature_collection.get('features', None)
    assert len(features) == 311
    feature_collection = p.query(
        cql_expression='name IS NOT NULL AND waterway NOT LIKE "d%"',
        limit=600)
    features = feature_collection.get('features', None)
    assert len(features) == 521
    feature_collection = p.query(
        cql_expression='name IS NOT NULL OR waterway LIKE "d%"',
        limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 200
    feature_collection = p.query(
        cql_expression='osm_id BETWEEN 600400000 AND 600500000',
        limit=50)
    features = feature_collection.get('features', None)
    assert len(features) == 37
    feature_collection = p.query(
        cql_expression='osm_id NOT BETWEEN 600400000 AND 600500000')
    features = feature_collection.get('features', None)
    assert len(features) == 10
    feature_collection = p.query(
        cql_expression='depth IS NULL')
    features = feature_collection.get('features', None)
    assert len(features) == 10
    feature_collection = p.query(
        cql_expression='width IS NOT NULL', limit=50)
    features = feature_collection.get('features', None)
    assert len(features) == 50
    feature_collection = p.query(
        cql_expression='waterway IN ("river","drain")',
        limit=600)
    features = feature_collection.get('features', None)
    assert len(features) == 593
    feature_collection = p.query(
        cql_expression='waterway NOT IN ("river","drain","stream")',
        limit=300)
    features = feature_collection.get('features', None)
    assert len(features) == 245


def test_cql_query_spatial(config):
    """Testing cql query for a valid JSON object with geometry for sqlite3"""

    p = PostgreSQLProvider(config)

    feature_collection = p.query(
        cql_expression='INTERSECTS(geometry,'
                       'MULTILINESTRING((29.269286692142487 '
                       '-3.3342012157851313, 29.269884824752808 '
                       '-3.3342159429633043)))')
    features = feature_collection.get('features', None)
    assert len(features) == 2

    feature_collection = p.query(
        cql_expression='CONTAINS(geometry, '
                       'MULTILINESTRING((29.2696894 -3.3346129, '
                       '29.2696838 -3.3348148)))', limit=20)
    features = feature_collection.get('features', None)
    assert len(features) == 1

    feature_collection = p.query(
        cql_expression='WITHIN(geometry,POLYGON((29.26920354366302 '
                       '-3.334880004586365, 29.26986336708069 '
                       '-3.334880004586365, 29.26986336708069 '
                       '-3.3338357139288632, 29.26920354366302 '
                       '-3.3338357139288632, 29.26920354366302 '
                       '-3.334880004586365)))')
    features = feature_collection.get('features', None)
    assert len(features) == 3
    feature_collection = p.query(
        cql_expression='TOUCHES(geometry,'
                       'MULTILINESTRING((29.269286692142487 '
                       '-3.3342012157851313, 29.269884824752808 '
                       '-3.3342159429633043)))')
    features = feature_collection.get('features', None)
    assert len(features) == 0
    feature_collection = p.query(
        cql_expression='DISJOINT(geometry,POINT(-81.95 44.93))',
        limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 200
    feature_collection = p.query(
        cql_expression='EQUALS(geometry,'
                       'MULTILINESTRING((29.2696894 -3.3346129, '
                       '29.2696838 -3.3348148)))')

    features = feature_collection.get('features', None)
    assert len(features) == 1
    feature_collection = p.query(
        cql_expression='CROSSES(geometry,'
                       'MULTILINESTRING((29.269286692142487 '
                       '-3.3342012157851313, 29.269884824752808 '
                       '-3.3342159429633043)))'
    )
    feature_collection = p.query(
        cql_expression='BEYOND(geometry,POINT(-85 75),100000,meters)',
        limit=20
    )
    features = feature_collection.get('features', None)
    assert len(features) == 0
    feature_collection = p.query(
        cql_expression='DWITHIN(geometry,POINT(-85 75),100,kilometers)',
        limit=20
    )
    features = feature_collection.get('features', None)
    assert len(features) == 20
    feature_collection = p.query(
        cql_expression='RELATE(geometry,POINT(-85 75), "T*****FF*")'
    )
    features = feature_collection.get('features', None)
    assert len(features) == 0
    feature_collection = p.query(
        cql_expression='BBOX(geometry, 29.3373, 3.4099, 29.3761, 3.3924)',
        limit=500)
    features = feature_collection.get('features', None)
    assert len(features) == 0


def test_cql_hits(config):
    """Testing result type hits for spatial CQL filter expression"""

    p = PostgreSQLProvider(config)
    results = p.query(
        resulttype='hits',
        cql_expression='EQUALS(geometry,'
                       'MULTILINESTRING((29.2696894 -3.3346129, '
                       '29.2696838 -3.3348148)))'
    )
    assert len(results['features']) == 0
    assert results['numberMatched'] == 1
    results = p.query(resulttype='hits',
                      cql_expression='waterway LIKE "d%"')
    assert len(results['features']) == 0
    assert results['numberMatched'] == 311


def test_auxiliary_cql_expressions(config):
    """Testing for incorrect CQL filter expression"""

    p = PostgreSQLProvider(config)
    try:
        results = p.query(cql_expression="waterway>'stream'")
        assert results.get('features', None) is None
        results = p.query(cql_expression="name@'Al%'")
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
