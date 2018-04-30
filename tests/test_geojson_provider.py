import json
import pytest

from pygeoapi.provider.geojson import GeoJSONProvider


path = '/tmp/test.geojson'


@pytest.fixture()
def fixture():
    data = {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [125.6, 10.1]},
            'properties': {
                'id': '123-456',
                'name': 'Dinagat Islands'}}]}

    with open(path, 'w') as fh:
        fh.write(json.dumps(data))
    return path


@pytest.fixture()
def config():
    return {
        'name': 'GeoJSON',
        'data': path,
        'id_field': 'id'
    }


def test_query(fixture, config):
    p = GeoJSONProvider(config)
    results = p.query()
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1
    assert results['features'][0]['properties']['id'] == '123-456'


def test_get(fixture, config):
    p = GeoJSONProvider(config)
    results = p.get('123-456')
    assert isinstance(results, dict)
    assert 'Dinagat' in results['properties']['name']


def test_delete(fixture, config):
    p = GeoJSONProvider(config)
    p.delete('123-456')

    results = p.query()
    assert len(results['features']) == 0


def test_create(fixture, config):
    p = GeoJSONProvider(config)
    new_feature = {
        'type': 'Feature',
        'ID': '123-456',
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
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]},
        'properties': {
            'id': '123-456',
            'name': 'Null Island'}}

    p.update('123-456', new_feature)

    # Should be changed
    results = p.get('123-456')
    assert 'Null' in results['properties']['name']


def test_update_safe_id(fixture, config):
    p = GeoJSONProvider(config)
    new_feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]},
        'properties': {
            'id': 'SOMETHING DIFFERENT',
            'name': 'Null Island'}}

    p.update('123-456', new_feature)

    # Don't let the id change, should not exist
    assert p.get('SOMETHING DIFFERENT') is None

    # Should still be at the old id
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
