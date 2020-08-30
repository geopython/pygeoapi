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

# Needs to be run like: pytest -s test_sqlite_provider.py
# In eclipse we need to set PYGEOAPI_CONFIG, Run>Debug Configurations>
# (Arguments as py.test and set external variables to the correct config path)

import pytest
import logging

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.sqlite import SQLiteGPKGProvider

LOGGER = logging.getLogger(__name__)


@pytest.fixture()
def config_sqlite():
    return {
        'name': 'SQLiteGPKG',
        'data': './tests/data/ne_110m_admin_0_countries.sqlite',
        'id_field': 'ogc_fid',
        'table': 'ne_110m_admin_0_countries'
    }


@pytest.fixture()
def config_geopackage():
    return {
        'name': 'SQLiteGPKG',
        'data': './tests/data/poi_portugal.gpkg',
        'id_field': 'osm_id',
        'table': 'poi_portugal'
    }


def test_query_sqlite(config_sqlite):
    """Testing query for a valid JSON object with geometry for sqlite3"""

    p = SQLiteGPKGProvider(config_sqlite)
    feature_collection = p.query()
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert features is not None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    geometry = feature.get('geometry', None)
    assert geometry is not None


def test_query_geopackage(config_geopackage):
    """Testing query for a valid JSON object with geometry for geopackage"""

    p = SQLiteGPKGProvider(config_geopackage)
    feature_collection = p.query()
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert features is not None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    geometry = feature.get('geometry', None)
    assert geometry is not None


def test_query_hits_sqlite_geopackage(config_sqlite):
    """Testing hits results type for sqlite/geopackage"""

    p = SQLiteGPKGProvider(config_sqlite)
    results = p.query(resulttype="hits")
    assert results["numberMatched"] == 177
    results = p.query(
        bbox=[28.3373, -5.4099, 32.3761, -3.3924],
        properties=[("continent", "Africa")], resulttype="hits")
    assert results["numberMatched"] == 3


def test_query_with_property_filter_sqlite_geopackage(config_sqlite):
    """Test query  valid features when filtering by property"""

    p = SQLiteGPKGProvider(config_sqlite)
    feature_collection = p.query(properties=[
        ("continent", "Europe")], limit=100)
    features = feature_collection.get('features', None)
    assert len(features) == 39


def test_query_with_property_filter_bbox_sqlite_geopackage(config_sqlite):
    """Test query  valid features when filtering by property"""
    p = SQLiteGPKGProvider(config_sqlite)
    feature_collection = p.query(properties=[("continent", "Europe")],
                                 bbox=[29.3373, -3.4099, 29.3761, -3.3924])
    features = feature_collection.get('features', None)
    assert len(features) == 0


def test_query_bbox_sqlite_geopackage(config_sqlite):
    """Test query with a specified bounding box"""

    psp = SQLiteGPKGProvider(config_sqlite)
    boxed_feature_collection = psp.query(
        bbox=[29.3373, -3.4099, 29.3761, -3.3924]
    )

    assert len(boxed_feature_collection['features']) == 1
    assert 'Burundi' in \
           boxed_feature_collection['features'][0]['properties']['name']


def test_get_sqlite(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    result = p.get(118)
    assert isinstance(result, dict)
    assert 'geometry' in result
    assert 'properties' in result
    assert 'id' in result
    assert 'Netherlands' in result['properties']['admin']


def test_get_geopackage(config_geopackage):
    p = SQLiteGPKGProvider(config_geopackage)
    result = p.get(536678593)
    assert isinstance(result, dict)
    assert 'geometry' in result
    assert 'properties' in result
    assert 'id' in result
    assert 'Académico' in result['properties']['name']


def test_get_sqlite_not_existing_item_raise_exception(config_sqlite):
    """Testing query for a not existing object"""
    p = SQLiteGPKGProvider(config_sqlite)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(1234567890)


def test_get_geopackage_not_existing_item_raise_exception(config_geopackage):
    """Testing query for a not existing object"""
    p = SQLiteGPKGProvider(config_geopackage)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_cql_query(config_sqlite):
    """Testing cql query for a valid JSON object with geometry for sqlite3"""

    p = SQLiteGPKGProvider(config_sqlite)

    feature_collection = p.query(
        cql_expression='continent = "Europe"', limit=100)
    features = feature_collection.get('features', None)
    assert len(features) == 39
    feature_collection = p.query(
        cql_expression='pop_year <> 2017', limit=100)
    features = feature_collection.get('features', None)
    assert len(features) == 5
    feature_collection = p.query(
        cql_expression='pop_year < 2017', limit=100)
    features = feature_collection.get('features', None)
    assert len(features) == 5
    feature_collection = p.query(
        cql_expression='pop_year <= 2017', limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 177
    feature_collection = p.query(
        cql_expression='pop_year > 2017', limit=100)
    features = feature_collection.get('features', None)
    assert len(features) == 0
    feature_collection = p.query(
        cql_expression='pop_year >= 2017', limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 172
    feature_collection = p.query(
        cql_expression='NOT continent = "Europe"',
        limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 138
    feature_collection = p.query(
        cql_expression='continent = "Europe" AND name LIKE "Al%"',
        limit=100)
    features = feature_collection.get('features', None)
    assert len(features) == 1
    feature_collection = p.query(
        cql_expression='continent = "Europe" OR name LIKE "Al%"',
        limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 40
    feature_collection = p.query(
        cql_expression='pop_year < 2017 AND name NOT ILIKE "%A"',
        limit=100)
    features = feature_collection.get('features', None)
    assert len(features) == 3
    feature_collection = p.query(
        cql_expression='pop_year BETWEEN 2017 AND 2019',
        limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 172
    feature_collection = p.query(
        cql_expression='pop_year NOT BETWEEN 2017 AND 2019')
    features = feature_collection.get('features', None)
    assert len(features) == 5
    feature_collection = p.query(
        cql_expression='admin IS NULL')
    features = feature_collection.get('features', None)
    assert len(features) == 0
    feature_collection = p.query(
        cql_expression='admin IS NOT NULL', limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 177
    feature_collection = p.query(
        cql_expression='admin IN ("Afghanistan","United Arab Emirates")',
        limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 2
    feature_collection = p.query(
        cql_expression='admin NOT IN ("Afghanistan","United Arab Emirates")',
        limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 175


def test_cql_query_spatial(config_sqlite):
    """Testing cql query for a valid JSON object with geometry for sqlite3"""

    p = SQLiteGPKGProvider(config_sqlite)

    feature_collection = p.query(
        cql_expression='INTERSECTS(geometry,POINT(51.57951867046327 '
                       '24.2454971379511))')
    features = feature_collection.get('features', None)
    assert len(features) == 1
    feature_collection = p.query(
        cql_expression='CONTAINS(geometry, POINT(116.05957031249999 '
                       '1.0546279422758869))', limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 1

    feature_collection = p.query(
        cql_expression='WITHIN(geometry,POLYGON((8.26171875 '
                       '39.198205348894795, 22.0166015625 '
                       '39.198205348894795, 22.0166015625 '
                       '49.32512199104001, 8.26171875 '
                       '49.32512199104001, 8.26171875 '
                       '39.198205348894795)))')
    features = feature_collection.get('features', None)
    assert len(features) == 7
    feature_collection = p.query(
        cql_expression='TOUCHES(geometry,'
                       'POLYGON((132.38645553588867 '
                       '-0.37112930169531927, '
                       '132.39495277404785 -0.37112930169531927, '
                       '132.39495277404785 '
                       '-0.3660653958674358, 132.38645553588867 '
                       '-0.3660653958674358, '
                       '132.38645553588867 -0.37112930169531927)))')
    features = feature_collection.get('features', None)
    assert len(features) == 0
    feature_collection = p.query(
        cql_expression='DISJOINT(geometry,POINT(-81.95 44.93))',
        limit=200)
    features = feature_collection.get('features', None)
    assert len(features) == 176
    feature_collection = p.query(
        cql_expression='EQUALS(geometry,'
                       'MULTIPOLYGON(((43.58274580259273 41.09214325618256, '
                       '44.97248009621807 41.24812856705559, '
                       '45.17949588397934 40.98535390885146, '
                       '45.56035118997044 40.81228953710592, '
                       '45.35917483905817 40.56150381119346, '
                       '45.89190717955509 40.21847565364001, '
                       '45.61001224140292 39.89999380142518, '
                       '46.03453413268064 39.62802073827307, '
                       '46.48349897643245 39.46415477147553, '
                       '46.50571984231797 38.77060537368629, '
                       '46.14362308124881 38.74120148371221, '
                       '45.73537926614301 39.31971914321974, '
                       '45.73997846861698 39.47399913182712, '
                       '43.58274580259273 41.09214325618256))))')

    features = feature_collection.get('features', None)
    assert len(features) == 0
    feature_collection = p.query(
        cql_expression='CROSSES(geometry,'
                       'LINESTRING(-84.86427616328001 47.86009630581028, '
                       '-84.86421380192041 47.86002792058838))'
    )
    features = feature_collection.get('features', None)
    assert len(features) == 0
    feature_collection = p.query(
        cql_expression='BEYOND(geometry,POINT(-85 75),100000,meters)',
        limit=200
    )
    features = feature_collection.get('features', None)
    assert len(features) == 121
    feature_collection = p.query(
        cql_expression='DWITHIN(geometry,POINT(-85 75),100,kilometers)',
        limit=200
    )
    features = feature_collection.get('features', None)
    assert len(features) == 56
    feature_collection = p.query(
        cql_expression='RELATE(geometry,POINT(-85 75), "T*****FF*")',
        limit=200
    )
    features = feature_collection.get('features', None)
    assert len(features) == 1
    feature_collection = p.query(
        cql_expression='BBOX(geometry, 9, 40, 22, 50)')
    features = feature_collection.get('features', None)
    assert len(features) == 10


def test_cql_hits(config_sqlite):
    """Testing result type hits for spatial CQL filter expression"""

    p = SQLiteGPKGProvider(config_sqlite)
    results = p.query(
        resulttype='hits',
        cql_expression='WITHIN(geometry,POLYGON((8.26171875 '
                       '39.198205348894795, 22.0166015625 '
                       '39.198205348894795, 22.0166015625 '
                       '49.32512199104001, 8.26171875 '
                       '49.32512199104001, 8.26171875 '
                       '39.198205348894795)))'
    )
    assert len(results['features']) == 0
    assert results['numberMatched'] == 7
    results = p.query(resulttype='hits', cql_expression='name LIKE "Al%"')
    assert len(results['features']) == 0
    assert results['numberMatched'] == 2


def test_auxiliary_cql_expressions(config_sqlite):
    """Testing for incorrect CQL filter expression"""

    p = SQLiteGPKGProvider(config_sqlite)
    try:
        results = p.query(cql_expression="name>'ALbania'")
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
