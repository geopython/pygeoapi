# Needs to be run like: python3 -m pytest

import pytest
from pygeoapi.provider.postgresql import PostgreSQLProvider


@pytest.fixture()
def config():
    return {
        'name': 'PostgreSQL',
        'data': {'host': '127.0.0.1',
                 'dbname': 'test',
                 'user': 'postgres',
                 'password': 'postgres'
                 },
        'id_field': "osm_id",
        'table': 'hotosm_bdi_waterways'
    }


def test_query(config):
    """Testing query for a valid JSON object with geometry"""

    p = PostgreSQLProvider(config)
    feature_collection = p.query()
    assert feature_collection.get('type', None) == "FeatureCollection"
    features = feature_collection.get('features', None)
    assert features is not None
    feature = features[0]
    properties = feature.get("properties", None)
    assert properties is not None
    geometry = feature.get("geometry", None)
    assert geometry is not None


def test_get(config):
    """Testing query for a specific object"""
    p = PostgreSQLProvider(config)
    results = p.get(29701937)
    print(results)
    assert len(results['features']) == 1
    assert "Kanyosha" in results['features'][0]['properties']['name']
