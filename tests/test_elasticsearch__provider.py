# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
# Copyright (c) 2024 Francesco Bartoli
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

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.elasticsearch_ import ElasticsearchProvider
from pygeoapi.models.cql import CQLModel


@pytest.fixture()
def config():
    return {
        'name': 'Elasticsearch',
        'type': 'feature',
        'data': 'http://localhost:9200/ne_110m_populated_places_simple',  # noqa
        'id_field': 'geonameid'
    }


@pytest.fixture()
def config_ordered_properties():
    return {
        'name': 'Elasticsearch',
        'type': 'feature',
        'data': 'http://localhost:9200/ne_110m_populated_places_simple',  # noqa
        'id_field': 'geonameid',
        'properties': [
            'adm0name',
            'adm1name'
        ]
    }


@pytest.fixture()
def config_cql():
    return {
        'name': 'Elasticsearch',
        'type': 'feature',
        'data': 'http://localhost:9200/nhsl_hazard_threat_all_indicators_s_bc',  # noqa
        'id_field': 'Sauid'
    }


@pytest.fixture()
def between():
    between_ = {
        "between": {
            "value": {"property": "properties.pop_max"},
            "lower": 10000,
            "upper": 100000
        }
    }
    return CQLModel.parse_obj(between_)


@pytest.fixture()
def between_upper():
    between_ = {
        "between": {
            "value": {"property": "properties.pop_max"},
            "upper": 100000
        }
    }
    return CQLModel.parse_obj(between_)


@pytest.fixture()
def between_lower():
    between_ = {
        "between": {
            "value": {"property": "properties.pop_max"},
            "lower": 10000
        }
    }
    return CQLModel.parse_obj(between_)


@pytest.fixture()
def eq():
    eq_ = {
        "eq": [
            {"property": "properties.featurecla"},
            "Admin-0 capital"
        ]
    }
    return CQLModel.parse_obj(eq_)


@pytest.fixture()
def _and(eq, between):
    and_ = {
        "and": [
            {
                "between": {
                    "value": {
                        "property": "properties.pop_max"
                    },
                    "lower": 100000,
                    "upper": 1000000
                }
            },
            {
                "eq": [
                    {"property": "properties.featurecla"},
                    "Admin-0 capital"
                ]
            }
        ]
    }
    return CQLModel.parse_obj(and_)


@pytest.fixture()
def intersects():
    intersects = {"intersects": [
        {"property": "geometry"},
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [10.497565, 41.520355],
                    [10.497565, 43.308645],
                    [15.111823, 43.308645],
                    [15.111823, 41.520355],
                    [10.497565, 41.520355]
                ]
            ]
        }
    ]}
    return CQLModel.parse_obj(intersects)


def test_query(config):
    p = ElasticsearchProvider(config)

    fields = p.get_fields()
    assert len(fields) == 37
    assert fields['scalerank']['type'] == 'number'
    assert fields['scalerank']['format'] == 'long'
    assert fields['changed']['type'] == 'number'
    assert fields['changed']['format'] == 'float'
    assert fields['ls_name']['type'] == 'string'

    results = p.query()
    assert len(results['features']) == 10
    assert results['numberMatched'] == 242
    assert results['numberReturned'] == 10
    assert results['features'][0]['id'] == 6691831
    assert results['features'][0]['properties']['nameascii'] == 'Vatican City'

    results = p.query(properties=[('nameascii', 'Vatican City')])
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == 6691831

    results = p.query(offset=2, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == 3042030

    results = p.query(sortby=[{'property': 'nameascii', 'order': '+'}])
    assert results['features'][0]['properties']['nameascii'] == 'Abidjan'

    results = p.query(sortby=[{'property': 'nameascii', 'order': '-'}])
    assert results['features'][0]['properties']['nameascii'] == 'Zagreb'

    results = p.query(sortby=[{'property': 'scalerank', 'order': '+'}])
    assert results['features'][0]['properties']['scalerank'] == 0

    results = p.query(sortby=[{'property': 'scalerank', 'order': '-'}])
    assert results['features'][0]['properties']['scalerank'] == 8

    assert len(results['features'][0]['properties']) == 37

    results = p.query(sortby=[{'property': 'nameascii', 'order': '-'}],
                      limit=10001)
    assert results['features'][0]['properties']['nameascii'] == 'Zagreb'
    assert len(results['features']) == 242
    assert results['numberMatched'] == 242
    assert results['numberReturned'] == 242

    results = p.query(select_properties=['nameascii'])
    assert len(results['features'][0]['properties']) == 1

    results = p.query(select_properties=['nameascii', 'scalerank'])
    assert len(results['features'][0]['properties']) == 2

    results = p.query(skip_geometry=True)
    assert results['features'][0]['geometry'] is None

    config['properties'] = ['nameascii']
    p = ElasticsearchProvider(config)
    results = p.query()
    assert len(results['features'][0]['properties']) == 1


def test_query_ordered_properties(config_ordered_properties):
    p = ElasticsearchProvider(config_ordered_properties)

    result = p.query()
    feature_properties = list(result['features'][0]['properties'].keys())

    assert feature_properties == ['adm0name', 'adm1name']


def test_get(config):
    p = ElasticsearchProvider(config)

    result = p.get('3413829')
    assert result['id'] == 3413829
    assert result['properties']['ls_name'] == 'Reykjavik'


def test_get_not_existing_item_raise_exception(config):
    """Testing query for a not existing object"""
    p = ElasticsearchProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get('404')


def test_post_cql_json_between_query(config, between):
    """Testing cql json query for a between object"""
    p = ElasticsearchProvider(config)

    results = p.query(limit=100, filterq=between)

    assert len(results['features']) == 23
    assert results['numberMatched'] == 23
    assert results['numberReturned'] == 23

    for item in results['features']:
        assert 10000 <= item["properties"]["pop_max"] <= 100000


def test_post_cql_json_between_lte_query(config, between_upper):
    """Testing cql json query for a between object"""
    p = ElasticsearchProvider(config)

    results = p.query(limit=100, filterq=between_upper)

    assert len(results['features']) == 28
    assert results['numberMatched'] == 28
    assert results['numberReturned'] == 28

    for item in results['features']:
        assert item["properties"]["pop_max"] <= 100000


def test_post_cql_json_between_gte_query(config, between_lower):
    """Testing cql json query for a between object"""
    p = ElasticsearchProvider(config)

    results = p.query(limit=500, filterq=between_lower)

    assert len(results['features']) == 237
    assert results['numberMatched'] == 237
    assert results['numberReturned'] == 237

    for item in results['features']:
        assert 10000 <= item["properties"]["pop_max"]


def test_post_cql_json_eq_query(config, eq):
    """Testing cql json query for an eq object"""
    p = ElasticsearchProvider(config)

    results = p.query(limit=500, filterq=eq)

    assert len(results['features']) == 235


def test_post_cql_json_and_query(config, _and):
    """Testing cql json query for an and object"""
    p = ElasticsearchProvider(config)

    results = p.query(limit=1000, filterq=_and)

    assert len(results['features']) == 77


def test_post_cql_json_intersects_query(config, intersects):
    """Testing cql json query for an intersects object"""
    p = ElasticsearchProvider(config)

    results = p.query(limit=100, filterq=intersects)

    assert len(results['features']) == 2
