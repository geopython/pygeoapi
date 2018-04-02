# Needs to be run like: pytest -s test_sqlite_provider.py
# In eclipse we need to set PYGEOAPI_CONFIG, Run>Debug Configurations>
# (Arguments as py.test and set external variables to the correct config path)

import pytest
from pygeoapi.provider.sqlite import SQLiteProvider


@pytest.fixture()
def config():
    return {
        'name': 'Sqlite',
        'data': './tests/data/ne_110m_admin_0_countries.sqlite',
        'id_field': "ogc_fid",
        'table': 'ne_110m_admin_0_countries'
    }


def test_query(config):
    """Testing query for a valid JSON object with geometry"""

    p = SQLiteProvider(config)
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
    p = SQLiteProvider(config)
    results = p.get(118)
    assert len(results['features']) == 1
    assert "Netherlands" in results['features'][0]['properties']['admin']
