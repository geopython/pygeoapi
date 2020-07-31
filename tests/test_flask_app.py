import pytest
import json

from pygeoapi.flask_app import APP as flask_app


@pytest.fixture
def app():
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_landing_page(app, client):
    res = client.get('/')
    assert res.status_code == 200
    assert res.headers['Content-Type'] == 'application/json'


# Facing CORS issue with this function
'''
def test_openapi(app, client):
    res = client.get('/openapi')
    assert res.status_code == 200
    assert res.headers['Content-Type'] == 'application/json'
    assert 'components' in json.loads(res.data.decode('utf-8'))
    assert 'paths' in json.loads(res.data.decode('utf-8'))
    assert 'tags' in json.loads(res.data.decode('utf-8'))
    assert 'servers' in json.loads(res.data.decode('utf-8'))
'''


def test_dataset_get(app, client):
    get_res = client.get('/collections/lakes/items/0')
    assert get_res.status_code == 200
    assert get_res.headers['Content-Type'] == 'application/json'
    assert json.loads(get_res.data.decode('utf-8'))['id'] == 0
    assert json.loads(get_res.data.decode('utf-8'))['properties']['name']\
        == 'Lake Baikal'


def test_dataset_get_non_existing_item(app, client):
    get_res = client.get('/collections/lakes/items/i_dont_exist')
    assert get_res.status_code == 404


def test_dataset_post(app, client):
    feature = {
        "type": "Feature",
        "id": 99,
        "properties": {
            "scalerank": 0,
            "name": "Lake Meza",
            "name_alt": "https://en.wikipedia.org/wiki/Lake_Meza",
            "admin": None,
            "featureclass": "Lake"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    106.57998579307912,
                    52.79998159444554
                ],
            ]
        }
    }
    get_res = client.get('/collections/lakes/items/99')
    if get_res.status_code == 404:
        post_res = client.post('/collections/lakes/items/',
                               json=feature)
        assert post_res.status_code == 201
        assert post_res.headers['Content-Type'] == 'application/json'
        assert post_res.headers['Location'] == \
            'http://localhost/collections/lakes/items/99'
        get_res = client.get('/collections/lakes/items/99')
        assert get_res.status_code == 200
    else:
        post_res = client.post('/collections/lakes/items/',
                               json=feature)
        pre = 'http://localhost/collections/lakes/items/'
        rand_id = post_res.headers['Location'][len(pre):]
        get_res = client.get('/collections/lakes/items/'+rand_id)
        assert get_res.status_code == 200


def test_dataset_post_existing_item(app, client):
    feature = {
        "type": "Feature",
        "id": 1,
        "properties": {
            "i_am_foreign": 1,
            "scalerank": 0,
            "name": "Lake Meza",
            "name_alt": "https://en.wikipedia.org/wiki/Lake_Meza",
            "admin": None,
            "featureclass": "Lake"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    106.57998579307912,
                    52.79998159444554
                ]
            ]
        }
    }

    post_res = client.post('/collections/lakes/items/', json=feature)
    assert post_res.status_code == 400


def test_dataset_post_invalid_schema(app, client):
    feature = {
        "type": "Feature",
        "id": 999,
        "properties": {
            "i_am_foreign": 1,
            "scalerank": 0,
            "name": "Lake Meza",
            "name_alt": "https://en.wikipedia.org/wiki/Lake_Meza",
            "admin": None,
            "featureclass": "Lake"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    106.57998579307912,
                    52.79998159444554
                ]
            ]
        }
    }

    post_res = client.post('/collections/lakes/items/', json=feature)
    assert post_res.status_code == 400


def test_dataset_put(app, client):
    feature = {
        "type": "Feature",
        "properties": {
            "scalerank": 0,
            "name": "Lake Lemu",
            "name_alt": "https://en.wikipedia.org/wiki/Lake_Lemu",
            "admin": None,
            "featureclass": "Lake"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    106.57998579307912,
                    52.79998159444554
                ]
            ]
        }
    }

    put_res = client.put('/collections/lakes/items/99',
                         json=feature)
    assert put_res.status_code == 200
    get_res = client.get('/collections/lakes/items/99')
    assert json.loads(get_res.data.decode('utf-8'))['properties']['name']\
        == 'Lake Lemu'


def test_dataset_put_non_existing_item(app, client):
    feature = {
        "type": "Feature",
        "properties": {
            "scalerank": 0,
            "name": "Lake Meza",
            "name_alt": "https://en.wikipedia.org/wiki/Lake_Meza",
            "admin": None,
            "featureclass": "Lake"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    106.57998579307912,
                    52.79998159444554
                ]
            ]
        }
    }

    put_res = client.put('/collections/lakes/items/i_dont_exist',
                         json=feature)
    assert put_res.status_code == 404


def test_dataset_put_invalid_schema(app, client):
    feature = {
        "type": "Feature",
        "id": 999,
        "properties": {
            "i_am_foreign": 1,
            "scalerank": 0,
            "name": "Lake Meza",
            "name_alt": "https://en.wikipedia.org/wiki/Lake_Meza",
            "admin": None,
            "featureclass": "Lake"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    106.57998579307912,
                    52.79998159444554
                ]
            ]
        }
    }

    put_res = client.put('/collections/lakes/items/99', json=feature)
    assert put_res.status_code == 400


def test_dataset_patch(app, client):
    updates = {
        "add": [{"name": "count", "value": 56}],
        "modify": [{"name": "name", "value": "Lake Zula"}],
        "remove": ["name_alt"]
    }

    patch_res = client.patch('/collections/lakes/items/99',
                             json=updates)
    assert patch_res.status_code == 200
    get_res = client.get('/collections/lakes/items/99')
    props = json.loads(get_res.data.decode('utf-8'))['properties']
    assert 'count' in props
    assert props['count'] == 56
    assert props['name'] == 'Lake Zula'
    assert 'datetime' not in props


def test_dataset_patch_non_existing_item(app, client):
    updates = {
        "add": [{"name": "new_attrib", "value": 100}],
        "modify": [],
        "remove": []
    }

    patch_res = client.patch('/collections/lakes/items/i_dont_exist',
                             json=updates)
    assert patch_res.status_code == 404


def test_dataset_patch_invalid_schema(app, client):
    updates = {
        "add": [{"name": "name", "value": "Lake Vladimer"}],
        "modify": [],
        "remove": []
    }

    patch_res = client.patch('/collections/lakes/items/99',
                             json=updates)
    assert patch_res.status_code == 400


def test_dataset_delete(app, client):
    delete_res = client.delete('/collections/lakes/items/99')
    assert delete_res.status_code == 200
    get_res = client.get('/collections/lakes/items/99')
    assert get_res.status_code == 404


def test_dataset_delete_non_existing_item(app, client):
    delete_res = client.delete('/collections/lakes/items/99')
    assert delete_res.status_code == 404
