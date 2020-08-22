from pygeoapi.starlette_app import app
from starlette.testclient import TestClient
import json


def test_landing_page():
    client = TestClient(app)
    res = client.get('/')
    assert res.status_code == 200
    assert res.headers['Content-Type'] == 'application/json'


def test_dataset_get():
    client = TestClient(app)
    get_res = client.get('/collections/lakes/items/0')
    assert get_res.status_code == 200
    assert get_res.headers['Content-Type'] == 'application/json'
    assert json.loads(get_res.content.decode('utf-8'))['properties']['id'] == 0
    assert json.loads(get_res.content.decode('utf-8'))['properties']['name']\
        == 'Lake Baikal'


def test_dataset_get_non_existing_item():
    client = TestClient(app)
    get_res = client.get('/collections/lakes/items/999999')
    assert get_res.status_code == 404


def test_dataset_post():
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
    client = TestClient(app)
    get_res = client.get('/collections/lakes/items/99')
    if get_res.status_code == 404:
        post_res = client.post('/collections/lakes/items/',
                               json=feature)
        assert post_res.status_code == 201
        assert post_res.headers['Content-Type'] == 'application/json'
        assert post_res.headers['Location'] == \
            '/collections/lakes/items/99'
        get_res = client.get('/collections/lakes/items/99')
        assert get_res.status_code == 200
    else:
        post_res = client.post('/collections/lakes/items/',
                               json=feature)
        pre = 'http://localhost/collections/lakes/items/'
        rand_id = post_res.headers['Location'][len(pre):]
        get_res = client.get('/collections/lakes/items/'+rand_id)
        assert get_res.status_code == 200


def test_dataset_post_existing_item():
    feature = {
        "type": "Feature",
        "id": 1,
        "properties": {
            "i_am_an_alien": 1,
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

    client = TestClient(app)
    post_res = client.post('/collections/lakes/items/', json=feature)
    assert post_res.status_code == 400


def test_dataset_post_invalid_schema():
    feature = {
        "type": "Feature",
        "id": 999,
        "properties": {
            "i_am_an_alien": 1,
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

    client = TestClient(app)
    post_res = client.post('/collections/lakes/items/', json=feature)
    assert post_res.status_code == 400


def test_dataset_put():
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

    client = TestClient(app)
    put_res = client.put('/collections/lakes/items/99',
                         json=feature)
    assert put_res.status_code == 200
    get_res = client.get('/collections/lakes/items/99')
    assert json.loads(get_res.content.decode('utf-8'))['properties']['name']\
        == 'Lake Lemu'


def test_dataset_put_non_existing_item():
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

    client = TestClient(app)
    put_res = client.put('/collections/lakes/items/999',
                         json=feature)
    assert put_res.status_code == 404


def test_dataset_put_invalid_schema():
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

    client = TestClient(app)
    put_res = client.put('/collections/lakes/items/99', json=feature)
    assert put_res.status_code == 400


def test_dataset_patch():
    updates = {
        "add": [{"name": "count", "value": 56}],
        "modify": [{"name": "name", "value": "Lake Zula"}],
        "remove": ["name_alt"]
    }

    client = TestClient(app)
    patch_res = client.patch('/collections/lakes/items/99',
                             json=updates)
    assert patch_res.status_code == 200
    get_res = client.get('/collections/lakes/items/99')
    props = json.loads(get_res.content.decode('utf-8'))['properties']
    assert 'count' in props
    assert props['count'] == 56
    assert props['name'] == 'Lake Zula'
    assert 'datetime' not in props


def test_dataset_patch_non_existing_item():
    updates = {
        "add": [{"name": "new_attrib", "value": 100}],
        "modify": [],
        "remove": []
    }

    client = TestClient(app)
    patch_res = client.patch('/collections/lakes/items/999',
                             json=updates)
    assert patch_res.status_code == 404


def test_dataset_patch_invalid_schema():
    updates = {
        "add": [{"name": "name", "value": "Lake Vladimer"}],
        "modify": [],
        "remove": []
    }

    client = TestClient(app)
    patch_res = client.patch('/collections/lakes/items/99',
                             json=updates)
    assert patch_res.status_code == 400


def test_dataset_delete():
    client = TestClient(app)
    delete_res = client.delete('/collections/lakes/items/99')
    assert delete_res.status_code == 200
    get_res = client.get('/collections/lakes/items/99')
    assert get_res.status_code == 404


def test_dataset_delete_non_existing_item():
    client = TestClient(app)
    delete_res = client.delete('/collections/lakes/items/99')
    assert delete_res.status_code == 404
