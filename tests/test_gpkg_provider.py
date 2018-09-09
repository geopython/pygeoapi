# Needs to be run like: pytest -s test_gpkg_provider.py
# In eclipse we need to set PYGEOAPI_CONFIG, Run>Debug Configurations>
# (Arguments as py.test and set external variables to the correct config path)


import pytest
from pygeoapi.provider.geopackage import GeoPackageProvider


@pytest.fixture()
def config():
    return {
        'name': 'GeoPackage',
        'data': './tests/data/poi_portugal.gpkg',
        'id_field': 'osm_id',
        'table': 'poi_portugal'
    }


def test_query(config):
    """Testing query for a valid JSON object with geometry"""

    p = GeoPackageProvider(config)
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
    p = GeoPackageProvider(config)
    results = p.get(5156778016)
    assert len(results['features']) == 1
    assert "tourist_info" in results['features'][0]['properties']['fclass']
