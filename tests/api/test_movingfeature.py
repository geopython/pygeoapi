from pygeoapi.provider.postgresql_mobilitydb import PostgresMobilityDB
import pytest
import json
from http import HTTPStatus
from pygeoapi.util import yaml_load

from tests.util import get_test_file_path, mock_api_request

from pygeoapi.api.movingfeatures import (
    manage_collection,
    manage_collection_item,
    manage_collection_item_tGeometry,
    manage_collection_item_tProperty,
    manage_collection_item_tProperty_value,
    get_collection_items,
    get_collection,
    get_collection_item,
    get_collection_items_tGeometry,
    get_collection_items_tGeometry_velocity,
    get_collection_items_tGeometry_distance,
    get_collection_items_tGeometry_acceleration,
    get_collection_items_tProperty,
    get_collection_items_tProperty_value)

from pygeoapi.api import API


@pytest.fixture()
def api_():
    with open(get_test_file_path('../pygeoapi-test-config-mfapi.yml')) as fh:
        config = yaml_load(fh)
    with open(get_test_file_path('../pygeoapi-test-openapi-mfapi.yml')) as fh:
        openapi = yaml_load(fh)
    return API(config, openapi)


@pytest.fixture(scope="session")
def context():
    return {}


@pytest.fixture()
def collection_property():
    return {
        "title": "moving_feature_collection_sample",
        "updateFrequency": 1000,
        "description": "example"
    }


@pytest.fixture()
def update_collection_property():
    return {
        "title": "moving_feature_collection_sample",
        "updateFrequency": 1000,
        "description": "test_update"
    }


@pytest.fixture()
def movingfeature():
    return {
        "type": "Feature",
        "crs": {
            "type": "Name",
            "properties": {
                "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
            }
        },
        "trs": {
            "type": "Link",
            "properties": {
                "type": "OGCDEF",
                "href": "http://www.opengis.net/def/uom/ISO-8601/0/Gregorian"
            }
        },
        "temporalGeometry": {
            "type": "MovingPoint",
            "datetimes": [
                "2011-07-14T22:01:01Z",
                "2011-07-14T22:01:02Z",
                "2011-07-14T22:01:03Z",
                "2011-07-14T22:01:04Z",
                "2011-07-14T22:01:05Z"
            ],
            "coordinates": [
                [
                    139.757083,
                    35.627701,
                    0.5
                ],
                [
                    139.757399,
                    35.627701,
                    2
                ],
                [
                    139.757555,
                    35.627688,
                    4
                ],
                [
                    139.757651,
                    35.627596,
                    4
                ],
                [
                    139.757716,
                    35.627483,
                    4
                ]
            ],
            "interpolation": "Linear",
            "base": {
                "type": "glTF",
                "href": "http://www.opengis.net/spec/movingfeatures/json/1.0/prism/example/car3dmodel.gltf"  # noqa
            },
            "orientations": [
                {
                    "scales": [
                        1,
                        1,
                        1
                    ],
                    "angles": [
                        0,
                        0,
                        0
                    ]
                },
                {
                    "scales": [
                        1,
                        1,
                        1
                    ],
                    "angles": [
                        0,
                        355,
                        0
                    ]
                },
                {
                    "scales": [
                        1,
                        1,
                        1
                    ],
                    "angles": [
                        0,
                        0,
                        330
                    ]
                },
                {
                    "scales": [
                        1,
                        1,
                        1
                    ],
                    "angles": [
                        0,
                        0,
                        300
                    ]
                },
                {
                    "scales": [
                        1,
                        1,
                        1
                    ],
                    "angles": [
                        0,
                        0,
                        270
                    ]
                }
            ]
        },
        "temporalProperties": [
            {
                "datetimes": [
                    "2011-07-14T22:01:01.450Z",
                    "2011-07-14T23:01:01.450Z",
                    "2011-07-15T00:01:01.450Z"
                ],
                "length": {
                    "type": "Measure",
                    "form": "http://www.qudt.org/qudt/owl/1.0.0/quantity/Length",  # noqa
                    "values": [
                        1,
                        2.4,
                        1
                    ],
                    "interpolation": "Linear"
                },
                "discharge": {
                    "type": "Measure",
                    "form": "MQS",
                    "values": [
                        3,
                        4,
                        5
                    ],
                    "interpolation": "Step"
                }
            },
            {
                "datetimes": [
                    1465621816590,
                    1465711526300
                ],
                "camera": {
                    "type": "Image",
                    "values": [
                        "http://www.opengis.net/spec/movingfeatures/json/1.0/prism/example/image1",  # noqa
                        "iVBORw0KGgoAAAANSUhEU......"
                    ],
                    "interpolation": "Discrete"
                },
                "labels": {
                    "type": "Text",
                    "values": [
                        "car",
                        "human"
                    ],
                    "interpolation": "Discrete"
                }
            }
        ],
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [
                    139.757083,
                    35.627701,
                    0.5
                ],
                [
                    139.757399,
                    35.627701,
                    2
                ],
                [
                    139.757555,
                    35.627688,
                    4
                ],
                [
                    139.757651,
                    35.627596,
                    4
                ],
                [
                    139.757716,
                    35.627483,
                    4
                ]
            ]
        },
        "properties": {
            "name": "car1",
            "state": "test1",
            "video": "http://www.opengis.net/spec/movingfeatures/json/1.0/prism/example/video.mpeg"  # noqa
        },
        "bbox": [
            139.757083,
            35.627483,
            0,
            139.757716,
            35.627701,
            4.5
        ],
        "time": [
            "2011-07-14T22:01:01Z",
            "2011-07-15T01:11:22Z"
        ],
        "id": "mf-1"
    }


@pytest.fixture()
def temporalgeometry():
    return {
        "type": "MovingPoint",
        "datetimes": [
            "2011-07-14T22:01:06Z",
            "2011-07-14T22:01:07Z",
            "2011-07-14T22:01:08Z",
            "2011-07-14T22:01:09Z",
            "2011-07-14T22:01:10Z"
        ],
        "coordinates": [
            [
                139.757083,
                35.627701,
                0.5
            ],
            [
                139.757399,
                35.627701,
                2
            ],
            [
                139.757555,
                35.627688,
                4
            ],
            [
                139.757651,
                35.627596,
                4
            ],
            [
                139.757716,
                35.627483,
                4
            ]
        ],
        "interpolation": "Linear",
        "base": {
            "type": "glTF",
            "href": "https://www.opengis.net/spec/movingfeatures/json/1.0/prism/example/car3dmodel.gltf"  # noqa
        },
        "orientations": [
            {
                "scales": [
                    1,
                    1,
                    1
                ],
                "angles": [
                    0,
                    0,
                    0
                ]
            },
            {
                "scales": [
                    1,
                    1,
                    1
                ],
                "angles": [
                    0,
                    355,
                    0
                ]
            },
            {
                "scales": [
                    1,
                    1,
                    1
                ],
                "angles": [
                    0,
                    0,
                    330
                ]
            },
            {
                "scales": [
                    1,
                    1,
                    1
                ],
                "angles": [
                    0,
                    0,
                    300
                ]
            },
            {
                "scales": [
                    1,
                    1,
                    1
                ],
                "angles": [
                    0,
                    0,
                    270
                ]
            }
        ]
    }


@pytest.fixture()
def temporalproperties():
    return [
        {
            "datetimes": [
                "2011-07-16T22:01:01.450Z",
                "2011-07-16T23:01:01.450Z",
                "2011-07-17T00:01:01.450Z"
            ],
            "length": {
                "type": "Measure",
                "form": "http://www.qudt.org/qudt/owl/1.0.0/quantity/Length",
                "values": [
                    1,
                    2.4,
                    1
                ],
                "interpolation": "Linear"
            },
            "discharge": {
                "type": "Measure",
                "form": "MQS",
                "values": [
                    3,
                    4,
                    5
                ],
                "interpolation": "Step"
            }
        },
        {
            "datetimes": [
                "2011-07-16T22:01:01.450Z",
                "2011-07-16T23:01:01.450Z"
            ],
            "camera": {
                "type": "Image",
                "values": [
                    "http://www.opengis.net/spec/movingfeatures/json/1.0/prism/example/image1",  # noqa
                    "iVBORw0KGgoAAAANSUhEU......"
                ],
                "interpolation": "Discrete"
            },
            "labels": {
                "type": "Text",
                "values": [
                    "car",
                    "human"
                ],
                "interpolation": "Discrete"
            }
        }
    ]


@pytest.fixture()
def temporalvalue_data():
    return {
        "datetimes": [
            "2011-07-18T08:00:00Z",
            "2011-07-18T08:00:01Z",
            "2011-07-18T08:00:02Z"
        ],
        "values": [
            0,
            20,
            50
        ],
        "interpolation": "Linear"
    }


def test_manage_collection_create(
        api_,
        collection_property,
        context):

    # missing request data
    req = mock_api_request()
    rsp_headers, code, response = manage_collection(api_, req, 'create')
    assert code == HTTPStatus.BAD_REQUEST

    # invalid request data
    req = mock_api_request(data='Invalid data. Valid data is JSON')
    rsp_headers, code, response = manage_collection(api_, req, 'create')
    assert code == HTTPStatus.BAD_REQUEST

    # successful request data
    req = mock_api_request(data=json.dumps(collection_property))
    rsp_headers, code, response = manage_collection(api_, req, 'create')
    assert code == HTTPStatus.CREATED
    assert response == ''
    assert rsp_headers['Content-Type'] == 'application/json'
    assert 'Location' in rsp_headers

    location = rsp_headers['Location']
    collection_id = location.split('/')[-1]
    assert collection_id is not None
    context['collection_id'] = collection_id


def test_manage_collection_item_create(
        api_, movingfeature, context):

    # collection not found
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item(
        api_, req, 'create', '00000000-0000-0000-0000-000000000000')
    assert code == HTTPStatus.NOT_FOUND

    # no data found
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item(
        api_, req, 'create', context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # invalid request data
    req = mock_api_request(data='Invalid data. Valid data is JSON')
    rsp_headers, code, response = manage_collection_item(
        api_, req, 'create', context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # The required tag (e.g., type,temporalgeometry)
    # is missing from the request data.
    missing_data = dict(movingfeature)
    del missing_data['temporalGeometry']

    req = mock_api_request(data=json.dumps(missing_data))
    rsp_headers, code, response = manage_collection_item(
        api_, req, 'create', context['collection_id'])
    assert code == HTTPStatus.NOT_IMPLEMENTED

    # successful request data
    req = mock_api_request(data=json.dumps(movingfeature))
    rsp_headers, code, response = manage_collection_item(
        api_, req, 'create', context['collection_id'])

    assert code == HTTPStatus.CREATED
    assert response == ''
    assert rsp_headers['Content-Type'] == 'application/json'
    assert 'Location' in rsp_headers

    location = rsp_headers['Location']
    mfeature_id = location.split('/')[-1]
    assert mfeature_id is not None
    context['mfeature_id'] = mfeature_id


def test_manage_collection_item_tGeometry_create(
        api_, temporalgeometry, context):

    # feature not found
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item_tGeometry(
        api_, req, 'create', '00000000-0000-0000-0000-000000000000',
        '00000000-0000-0000-0000-000000000000')
    assert code == HTTPStatus.NOT_FOUND

    # no data found
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item_tGeometry(
        api_, req, 'create', context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # invalid request data
    req = mock_api_request(data='Invalid data. Valid data is JSON')
    rsp_headers, code, response = manage_collection_item_tGeometry(
        api_, req, 'create', context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # The required tag (e.g., type,prisms)
    # is missing from the request data.
    missing_data = dict(temporalgeometry)
    del missing_data['type']

    req = mock_api_request(data=json.dumps(missing_data))
    rsp_headers, code, response = manage_collection_item_tGeometry(
        api_, req, 'create', context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.NOT_IMPLEMENTED

    # successful request data
    req = mock_api_request(data=json.dumps(temporalgeometry))
    rsp_headers, code, response = manage_collection_item_tGeometry(
        api_, req, 'create', context['collection_id'], context['mfeature_id'])

    assert code == HTTPStatus.CREATED
    assert response == ''
    assert rsp_headers['Content-Type'] == 'application/json'
    assert 'Location' in rsp_headers

    location = rsp_headers['Location']
    tgeometry_id = location.split('/')[-1]
    assert tgeometry_id is not None
    context['tgeometry_id'] = tgeometry_id


def test_manage_collection_item_tProperty_create(
        api_, temporalproperties, context):

    # feature not found
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item_tProperty(
        api_, req, 'create', '00000000-0000-0000-0000-000000000000',
        '00000000-0000-0000-0000-000000000000')
    assert code == HTTPStatus.NOT_FOUND

    # no data found
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item_tProperty(
        api_, req, 'create', context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # invalid request data
    req = mock_api_request(data='Invalid data. Valid data is JSON')
    rsp_headers, code, response = manage_collection_item_tProperty(
        api_, req, 'create', context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # The required tag (e.g., datetimes,interpolation)
    # is missing from the request data.
    missing_data = []
    for temporalproperty in temporalproperties:
        missing_data.append(dict(temporalproperty))
    del missing_data[0]['datetimes']

    req = mock_api_request(data=json.dumps(missing_data, indent=2))
    rsp_headers, code, response = manage_collection_item_tProperty(
        api_, req, 'create', context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.NOT_IMPLEMENTED

    # successful request data
    req = mock_api_request(data=json.dumps(temporalproperties, indent=2))
    rsp_headers, code, response = manage_collection_item_tProperty(
        api_, req, 'create', context['collection_id'], context['mfeature_id'])

    assert code == HTTPStatus.CREATED
    assert response == ''
    assert rsp_headers['Content-Type'] == 'application/json'
    assert 'Locations' in rsp_headers

    location = rsp_headers['Locations']
    assert len(location) == 4
    tProperty_name = location[-1].split('/')[-1]
    assert tProperty_name is not None
    context['tProperty_name'] = tProperty_name


def test_manage_collection_item_tProperty_value_create(
        api_, temporalvalue_data, context):

    # temporal property not found
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item_tProperty_value(
        api_, req, 'create', '00000000-0000-0000-0000-000000000000',
        '00000000-0000-0000-0000-000000000000', '')
    assert code == HTTPStatus.NOT_FOUND

    # no data found
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item_tProperty_value(
        api_, req, 'create', context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])
    assert code == HTTPStatus.BAD_REQUEST

    # invalid request data
    req = mock_api_request(data='Invalid data. Valid data is JSON')
    rsp_headers, code, response = manage_collection_item_tProperty_value(
        api_, req, 'create', context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])
    assert code == HTTPStatus.BAD_REQUEST

    # The required tag (e.g., datetimes,interpolation)
    # is missing from the request data.
    missing_data = dict(temporalvalue_data)
    del missing_data['datetimes']

    req = mock_api_request(data=json.dumps(missing_data))
    rsp_headers, code, response = manage_collection_item_tProperty_value(
        api_, req, 'create', context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])
    assert code == HTTPStatus.NOT_IMPLEMENTED

    # successful request data
    req = mock_api_request(data=json.dumps(temporalvalue_data))
    rsp_headers, code, response = manage_collection_item_tProperty_value(
        api_, req, 'create', context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])

    assert code == HTTPStatus.CREATED
    assert response == ''
    assert rsp_headers['Content-Type'] == 'application/json'
    assert 'Location' in rsp_headers

    location = rsp_headers['Location']
    tvalue_id = location.split('/')[-1]
    assert tvalue_id is not None
    context['tvalue_id'] = tvalue_id


def test_manage_collection_update(
        api_,
        update_collection_property,
        context):

    # missing request data
    req = mock_api_request()
    rsp_headers, code, response = manage_collection(
        api_, req, 'update', context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # invalid request data
    req = mock_api_request(data='Invalid data. Valid data is JSON')
    rsp_headers, code, response = manage_collection(
        api_, req, 'update', context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # successful request data
    req = mock_api_request(data=json.dumps(update_collection_property))
    rsp_headers, code, response = manage_collection(
        api_, req, 'update', context['collection_id'])

    assert code == HTTPStatus.NO_CONTENT
    assert response == ''


def test_get_collection_items(api_, context):

    # not found
    req = mock_api_request()
    rsp_headers, code, response = get_collection_items(
        api_, req, '00000000-0000-0000-0000-000000000000')
    assert code == HTTPStatus.NOT_FOUND

    # offset value should be positive or zero
    req = mock_api_request({'offset': -1})
    rsp_headers, code, response = get_collection_items(
        api_, req, context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # offset value should be an integer
    req = mock_api_request({'offset': 'one'})
    rsp_headers, code, response = get_collection_items(
        api_, req, context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # limit value should be strictly positive
    req = mock_api_request({'offset': 0, 'limit': 0})
    rsp_headers, code, response = get_collection_items(
        api_, req, context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # limit value should be less than or equal to 10000
    req = mock_api_request({'offset': 0, 'limit': 10001})
    rsp_headers, code, response = get_collection_items(
        api_, req, context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # limit value should be an integer
    req = mock_api_request({'offset': 0, 'limit': 'one'})
    rsp_headers, code, response = get_collection_items(
        api_, req, context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # bbox values must be numbers
    req = mock_api_request(
        {'offset': 0, 'limit': 10, 'bbox': 'one,two,three,four'})
    rsp_headers, code, response = get_collection_items(
        api_, req, context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # bbox should be 4 values (minx,miny,maxx,maxy) or 6 values
    # (minx,miny,minz,maxx,maxy,maxz)
    req = mock_api_request(
        {'offset': 0, 'limit': 10, 'bbox': '100,30,0,200,40'})
    rsp_headers, code, response = get_collection_items(
        api_, req, context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # minx is greater than maxx (possibly antimeridian bbox)
    req = mock_api_request(
        {'offset': 0, 'limit': 10, 'bbox': '200,30,0,100,40,10'})
    rsp_headers, code, response = get_collection_items(
        api_, req, context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # datetime parameter out of range
    req = mock_api_request({'offset': 0,
                            'limit': 10,
                            'bbox': '100,30,0,200,40,10',
                            'datetime': '2011-07-14T23:01:01.000Z/2011-07-14T22:01:01.000Z'})  # noqa
    rsp_headers, code, response = get_collection_items(
        api_, req, context['collection_id'])
    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'offset': 0,
                            'limit': 10,
                            'bbox': '100,30,0,200,40,10',
                            'datetime': '2011-07-14T22:01:01.000Z/2011-07-14T23:01:01.000Z',  # noqa
                            'subTrajectory': 'true'})
    rsp_headers, code, response = get_collection_items(
        api_, req, context['collection_id'])
    assert code == HTTPStatus.OK

    assert rsp_headers['Content-Type'] == 'application/json'
    collection = json.loads(response)

    # check response data
    assert 'type' in collection
    assert 'features' in collection
    assert len(collection['features']) == 1

    mfeature = collection['features'][0]
    assert 'id' in mfeature
    assert 'type' in mfeature
    assert mfeature['type'] == 'Feature'
    assert 'properties' in mfeature

    assert 'geometry' in mfeature
    assert 'type' in mfeature['geometry']
    assert 'coordinates' in mfeature['geometry']

    assert 'temporalGeometry' in mfeature
    assert len(mfeature['temporalGeometry']) == 2
    temporal_geometry = mfeature['temporalGeometry'][0]
    assert 'type' in temporal_geometry
    assert temporal_geometry['type'] == 'MovingPoint'
    assert 'datetimes' in temporal_geometry
    assert 'interpolation' in temporal_geometry
    assert 'id' in temporal_geometry

    assert 'bbox' in mfeature
    assert mfeature['bbox'] == [
        139.757083,
        35.627483,
        0.5,
        139.757716,
        35.627701,
        4]
    assert 'time' in mfeature
    assert mfeature['time'] == ["2011-07-14T22:01:01Z", "2011-07-15T01:11:22Z"]

    assert 'crs' in collection
    assert 'trs' in collection

    assert 'links' in collection
    assert len(collection['links']) == 1

    assert 'timeStamp' in collection
    assert 'numberMatched' in collection
    assert collection['numberMatched'] == 1
    assert 'numberReturned' in collection
    assert collection['numberReturned'] == 1


def test_get_collection(api_, context):

    # not found
    req = mock_api_request()
    rsp_headers, code, response = get_collection(
        api_, req, '00000000-0000-0000-0000-000000000000')
    assert code == HTTPStatus.NOT_FOUND

    # successful data
    req = mock_api_request()
    rsp_headers, code, response = get_collection(
        api_, req, context['collection_id'])
    assert code == HTTPStatus.OK

    assert rsp_headers['Content-Type'] == 'application/json'
    collection = json.loads(response)

    assert 'id' in collection
    assert 'itemType' in collection
    assert collection['itemType'] == 'movingfeature'

    assert 'title' in collection
    assert collection['title'] == 'moving_feature_collection_sample'
    assert 'updateFrequency' in collection
    assert collection['updateFrequency'] == 1000
    assert 'description' in collection
    assert collection['description'] == 'test_update'

    assert 'extent' in collection
    assert collection['extent']['spatial']['bbox'] == [
        139.757083, 35.627483, 0.5, 139.757716, 35.627701, 4]
    assert collection['extent']['spatial']['crs'] == \
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
    assert collection['extent']['temporal']['interval'] == \
        ["2011-07-14T22:01:01Z", "2011-07-15T01:11:22Z"]
    assert collection['extent']['temporal']['trs'] == \
        'http://www.opengis.net/def/uom/ISO-8601/0/Gregorian'

    assert 'links' in collection
    assert len(collection['links']) == 1


def test_get_collection_item(api_, context):

    # not found
    req = mock_api_request()
    rsp_headers, code, response = get_collection_item(
        api_, req, '00000000-0000-0000-0000-000000000000',
        '00000000-0000-0000-0000-000000000000')
    assert code == HTTPStatus.NOT_FOUND

    # successful data
    rsp_headers, code, response = get_collection_item(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.OK

    assert rsp_headers['Content-Type'] == 'application/json'
    mfeature = json.loads(response)

    assert 'id' in mfeature
    assert 'type' in mfeature
    assert mfeature['type'] == 'Feature'
    assert 'properties' in mfeature

    assert 'geometry' in mfeature
    assert 'type' in mfeature['geometry']
    assert 'coordinates' in mfeature['geometry']

    assert 'crs' in mfeature
    assert 'trs' in mfeature

    assert 'bbox' in mfeature
    assert mfeature['bbox'] == [
        139.757083,
        35.627483,
        0.5,
        139.757716,
        35.627701,
        4]
    assert 'time' in mfeature
    assert mfeature['time'] == ["2011-07-14T22:01:01Z", "2011-07-15T01:11:22Z"]

    assert 'links' in mfeature
    assert len(mfeature['links']) == 1


def test_get_collection_items_tGeometry(api_, context):

    # not found
    req = mock_api_request()
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, '00000000-0000-0000-0000-000000000000',
        '00000000-0000-0000-0000-000000000000')
    assert code == HTTPStatus.NOT_FOUND

    # offset value should be positive or zero
    req = mock_api_request({'offset': -1})
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # offset value should be an integer
    req = mock_api_request({'offset': 'one'})
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # limit value should be strictly positive
    req = mock_api_request({'offset': 0, 'limit': 0})
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # limit value should be less than or equal to 10000
    req = mock_api_request({'offset': 0, 'limit': 10001})
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # limit value should be an integer
    req = mock_api_request({'offset': 0, 'limit': 'one'})
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # bbox values must be numbers
    req = mock_api_request(
        {'offset': 0, 'limit': 10, 'bbox': 'one,two,three,four'})
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # bbox should be 4 values (minx,miny,maxx,maxy) or 6 values
    # (minx,miny,minz,maxx,maxy,maxz)
    req = mock_api_request(
        {'offset': 0, 'limit': 10, 'bbox': '100,30,0,200,40'})
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # minx is greater than maxx (possibly antimeridian bbox)
    req = mock_api_request(
        {'offset': 0, 'limit': 10, 'bbox': '200,30,0,100,40,10'})
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # invalid leaf
    req = mock_api_request({'offset': 0,
                            'limit': 10,
                            'bbox': '100,30,0,200,40,10',
                            'leaf': '2011-07-14T22:01:01.000Z,2011-07-14T22:01:01.000Z'})  # noqa
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, context['collection_id'], context['mfeature_id'])

    assert code == HTTPStatus.BAD_REQUEST

    # cannot use both parameter `subTrajectory` and `leaf` at the same time
    req = mock_api_request({'offset': 0,
                            'limit': 10,
                            'bbox': '100,30,0,200,40,10',
                            'leaf': '2011-07-14T22:01:01.000Z',
                            'subTrajectory': True})
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # datetime parameter out of range
    req = mock_api_request({'offset': 0,
                            'limit': 10,
                            'bbox': '100,30,0,200,40,10',
                            'leaf': '2011-07-14T22:01:01.000Z',
                            'datetime': '2011-07-14T23:01:01.000Z/2011-07-14T22:01:01.000Z'})  # noqa
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # successful data
    req = mock_api_request({'offset': 0,
                            'limit': 10,
                            'bbox': '100,30,0,200,40,10',
                            'leaf': '2011-07-14T22:01:01.000Z',
                            'datetime': '2011-07-14T22:01:01.000Z/2011-07-14T23:01:01.000Z'})  # noqa
    rsp_headers, code, response = get_collection_items_tGeometry(
        api_, req, context['collection_id'], context['mfeature_id'])

    assert code == HTTPStatus.OK

    assert rsp_headers['Content-Type'] == 'application/json'
    temporal_geometries = json.loads(response)

    assert 'geometrySequence' in temporal_geometries
    assert len(temporal_geometries["geometrySequence"]) == 1

    temporal_geometry = temporal_geometries['geometrySequence'][0]
    assert 'id' in temporal_geometry
    assert 'datetimes' in temporal_geometry
    assert temporal_geometry['datetimes'] == ["2011-07-14T22:01:01+09"]
    assert 'coordinates' in temporal_geometry
    assert temporal_geometry['coordinates'] == [[139.757083, 35.627701, 0.5]]
    assert 'type' in temporal_geometry
    assert temporal_geometry['type'] == 'MovingPoint'
    assert 'interpolation' in temporal_geometry
    assert temporal_geometry['interpolation'] == 'Linear'

    assert 'crs' in temporal_geometries
    assert 'trs' in temporal_geometries
    assert 'links' in temporal_geometries
    assert len(temporal_geometries['links']) == 1

    assert 'timeStamp' in temporal_geometries
    assert 'numberMatched' in temporal_geometries
    assert temporal_geometries['numberMatched'] == 2
    assert 'numberReturned' in temporal_geometries
    assert temporal_geometries['numberReturned'] == 1


def test_get_collection_items_tGeometry_velocity(api_, context):

    # successful data
    req = mock_api_request({'date-time': '2011-07-14T22:01:08Z'})
    rsp_headers, code, response = get_collection_items_tGeometry_velocity(
        api_, req, context['collection_id'], context['mfeature_id'],
        context['tgeometry_id'])
    assert code == HTTPStatus.OK

    assert rsp_headers['Content-Type'] == 'application/json'
    temporal_properties = response

    assert 'name' in temporal_properties
    assert temporal_properties['name'] == 'velocity'
    assert 'type' in temporal_properties
    assert temporal_properties['type'] == 'TReal'
    assert 'form' in temporal_properties
    assert temporal_properties['form'] == 'MTS'

    assert 'valueSequence' in temporal_properties
    assert len(temporal_properties['valueSequence']) == 1
    value_sequence = temporal_properties['valueSequence'][0]

    assert 'datetimes' in value_sequence
    assert value_sequence['datetimes'] == ["2011-07-14T22:01:08.000000Z"]
    assert 'values' in value_sequence
    assert value_sequence['values'] == [0.00013296616111996862]
    assert 'interpolation' in value_sequence
    assert value_sequence['interpolation'], 1 == "Discrete"


def test_get_collection_items_tGeometry_distance(api_, context):

    # successful data
    req = mock_api_request({'date-time': '2011-07-14T22:01:08Z'})
    rsp_headers, code, response = get_collection_items_tGeometry_distance(
        api_, req, context['collection_id'], context['mfeature_id'],
        context['tgeometry_id'])
    assert code == HTTPStatus.OK

    assert rsp_headers['Content-Type'] == 'application/json'
    temporal_properties = response

    assert 'name' in temporal_properties
    assert temporal_properties['name'] == 'distance'
    assert 'type' in temporal_properties
    assert temporal_properties['type'] == 'TReal'
    assert 'form' in temporal_properties
    assert temporal_properties['form'] == 'MTR'

    assert 'valueSequence' in temporal_properties
    assert len(temporal_properties['valueSequence']) == 1
    value_sequence = temporal_properties['valueSequence'][0]

    assert 'datetimes' in value_sequence
    assert value_sequence['datetimes'] == ["2011-07-14T22:01:08.000000Z"]
    assert 'values' in value_sequence
    assert value_sequence['values'] == [3.5000000394115824]
    assert 'interpolation' in value_sequence
    assert value_sequence['interpolation'], 1 == "Discrete"


def test_get_collection_items_tGeometry_acceleration(api_, context):

    # successful data
    req = mock_api_request({'date-time': '2011-07-14T22:01:08Z'})
    rsp_headers, code, response = \
        get_collection_items_tGeometry_acceleration(
            api_, req, context['collection_id'], context['mfeature_id'],
            context['tgeometry_id'])
    assert code == HTTPStatus.OK

    assert rsp_headers['Content-Type'] == 'application/json'
    temporal_properties = response

    assert 'name' in temporal_properties
    assert temporal_properties['name'] == 'acceleration'
    assert 'type' in temporal_properties
    assert temporal_properties['type'] == 'TReal'
    assert 'form' in temporal_properties
    assert temporal_properties['form'] == 'MTS'

    assert 'valueSequence' in temporal_properties
    assert len(temporal_properties['valueSequence']) == 1
    value_sequence = temporal_properties['valueSequence'][0]

    assert 'datetimes' in value_sequence
    assert value_sequence['datetimes'] == ["2011-07-14T22:01:08.000000Z"]
    assert 'values' in value_sequence
    assert value_sequence['values'] == [0]
    assert 'interpolation' in value_sequence
    assert value_sequence['interpolation'], 1 == "Discrete"


def test_get_collection_items_tProperty(api_, context):

    # not found
    req = mock_api_request()
    rsp_headers, code, response = get_collection_items_tProperty(
        api_, req, '00000000-0000-0000-0000-000000000000',
        '00000000-0000-0000-0000-000000000000')
    assert code == HTTPStatus.NOT_FOUND

    # offset value should be positive or zero
    req = mock_api_request({'offset': -1})
    rsp_headers, code, response = get_collection_items_tProperty(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # offset value should be an integer
    req = mock_api_request({'offset': 'one'})
    rsp_headers, code, response = get_collection_items_tProperty(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # limit value should be strictly positive
    req = mock_api_request({'offset': 0, 'limit': 0})
    rsp_headers, code, response = get_collection_items_tProperty(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # limit value should be less than or equal to 10000
    req = mock_api_request({'offset': 0, 'limit': 10001})
    rsp_headers, code, response = get_collection_items_tProperty(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # limit value should be an integer
    req = mock_api_request({'offset': 0, 'limit': 'one'})
    rsp_headers, code, response = get_collection_items_tProperty(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # datetime parameter out of range
    req = mock_api_request({'offset': 0, 'limit': 10,
                       'datetime': '2011-07-17T22:01:01.450Z/2011-07-16T00:01:01.450Z'})  # noqa
    rsp_headers, code, response = get_collection_items_tProperty(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.BAD_REQUEST

    # successful data
    req = mock_api_request({'offset': 0,
                            'limit': 10,
                            'datetime': '2011-07-16T22:01:01.450Z/2011-07-17T00:01:01.450Z',  # noqa
                            'subTemporalValue': 'true'})
    rsp_headers, code, response = get_collection_items_tProperty(
        api_, req, context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.OK

    assert rsp_headers['Content-Type'] == 'application/json'
    result = json.loads(response)

    assert 'temporalProperties' in result
    temporal_properties = result['temporalProperties']
    assert len(temporal_properties) == 2

    temporal_property = temporal_properties[0]
    assert 'datetimes' in temporal_property
    assert 'discharge' in temporal_property
    assert 'form' in temporal_property['discharge']
    assert temporal_property['discharge']['form'] == 'MQS'
    assert 'type' in temporal_property['discharge']
    assert temporal_property['discharge']['type'] == 'Measure'
    assert 'values' in temporal_property['discharge']
    assert temporal_property['discharge']['values'] == [3, 4, 5]

    assert 'length' in temporal_property
    assert 'form' in temporal_property['length']
    assert temporal_property['length']['form'] == \
        'http://www.qudt.org/qudt/owl/1.0.0/quantity/Length'
    assert 'type' in temporal_property['length']
    assert temporal_property['length']['type'] == 'Measure'
    assert 'values' in temporal_property['length']
    assert temporal_property['length']['values'] == [1, 2.4, 1]

    assert 'links' in result
    assert len(result['links']) == 1

    assert 'timeStamp' in result
    assert 'numberMatched' in result
    assert result['numberMatched'] == 4
    assert 'numberReturned' in result
    assert result['numberReturned'] == 4


def test_get_collection_items_tProperty_value(api_, context):

    # not found
    req = mock_api_request()
    rsp_headers, code, response = get_collection_items_tProperty_value(
        api_, req, '00000000-0000-0000-0000-000000000000',
        '00000000-0000-0000-0000-000000000000', '')
    assert code == HTTPStatus.NOT_FOUND

    # offset value should be positive or zero
    req = mock_api_request({'offset': -1})
    rsp_headers, code, response = get_collection_items_tProperty_value(
        api_, req, context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])
    assert code == HTTPStatus.BAD_REQUEST

    # offset value should be an integer
    req = mock_api_request({'offset': 'one'})
    rsp_headers, code, response = get_collection_items_tProperty_value(
        api_, req, context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])
    assert code == HTTPStatus.BAD_REQUEST

    # limit value should be strictly positive
    req = mock_api_request({'offset': 0, 'limit': 0})
    rsp_headers, code, response = get_collection_items_tProperty_value(
        api_, req, context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])
    assert code == HTTPStatus.BAD_REQUEST

    # limit value should be less than or equal to 10000
    req = mock_api_request({'offset': 0, 'limit': 10001})
    rsp_headers, code, response = get_collection_items_tProperty_value(
        api_, req, context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])
    assert code == HTTPStatus.BAD_REQUEST

    # limit value should be an integer
    req = mock_api_request({'offset': 0, 'limit': 'one'})
    rsp_headers, code, response = get_collection_items_tProperty_value(
        api_, req, context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])
    assert code == HTTPStatus.BAD_REQUEST

    # invalid leaf
    req = mock_api_request({'offset': 0, 'limit': 10,
                        'leaf': '2011-07-14T22:01:01.000Z,2011-07-14T22:01:01.000Z'})  # noqa
    rsp_headers, code, response = get_collection_items_tProperty_value(
        api_, req, context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])
    assert code == HTTPStatus.BAD_REQUEST

    # cannot use both parameter `subTemporalValue`
    # and `leaf` at the same time
    req = mock_api_request({'offset': 0,
                            'limit': 10,
                            'leaf': '2011-07-16T22:01:01.450Z',
                            'subTemporalValue': True})
    rsp_headers, code, response = get_collection_items_tProperty_value(
        api_, req, context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])
    assert code == HTTPStatus.BAD_REQUEST

    # datetime parameter out of range
    req = mock_api_request({'offset': 0,
                            'limit': 10,
                            'leaf': '2011-07-16T22:01:01.450Z',
                            'datetime': '2011-07-17T22:01:01.450Z/2011-07-16T00:01:01.450Z'})  # noqa
    rsp_headers, code, response = get_collection_items_tProperty_value(
        api_, req, context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])
    assert code == HTTPStatus.BAD_REQUEST

    # successful data
    req = mock_api_request({'offset': 0,
                            'limit': 10,
                            'leaf': '2011-07-16T22:01:01.450Z',
                            'datetime': '2011-07-16T22:01:01.450Z/2011-07-17T00:01:01.450Z'})  # noqa
    rsp_headers, code, response = get_collection_items_tProperty_value(
        api_, req, context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])

    assert code == HTTPStatus.OK

    assert rsp_headers['Content-Type'] == 'application/json'
    tProperty_value = json.loads(response)

    assert 'type' in tProperty_value
    assert tProperty_value['type'] == 'Text'
    assert 'valueSequence' in tProperty_value
    assert len(tProperty_value["valueSequence"]) == 1

    valueSequence = tProperty_value['valueSequence'][0]
    assert 'values' in valueSequence
    assert valueSequence['values'] == ["car"]
    assert 'datetimes' in valueSequence
    assert valueSequence['datetimes'] == ["2011-07-16T22:01:01.45Z"]
    assert 'interpolation' in valueSequence
    assert valueSequence['interpolation'] == 'Discrete'


def test_manage_collection_item_tProperty_value_delete(
        api_, context):

    # feature not found
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item_tProperty_value(
        api_, req, 'delete', '00000000-0000-0000-0000-000000000000',
        '00000000-0000-0000-0000-000000000000', '',
        '00000000-0000-0000-0000-000000000000')
    assert code == HTTPStatus.NOT_FOUND

    # successful delete
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item_tProperty_value(
        api_, req, 'delete', context['collection_id'], context['mfeature_id'],
        context['tProperty_name'], context['tvalue_id'])

    assert code == HTTPStatus.NO_CONTENT
    assert response == ''
    assert rsp_headers['Content-Type'] == 'application/json'


def test_manage_collection_item_tProperty_delete(
        api_, context):

    # feature not found
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item_tProperty(
        api_, req, 'delete', '00000000-0000-0000-0000-000000000000',
        '00000000-0000-0000-0000-000000000000', '')
    assert code == HTTPStatus.NOT_FOUND

    # successful delete
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item_tProperty(
        api_, req, 'delete', context['collection_id'], context['mfeature_id'],
        context['tProperty_name'])

    assert code == HTTPStatus.NO_CONTENT
    assert response == ''
    assert rsp_headers['Content-Type'] == 'application/json'


def test_manage_collection_item_tGeometry_delete(
        api_, context):

    # feature not found
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item_tGeometry(
        api_, req, 'delete', '00000000-0000-0000-0000-000000000000',
        '00000000-0000-0000-0000-000000000000',
        '00000000-0000-0000-0000-000000000000')
    assert code == HTTPStatus.NOT_FOUND

    # successful delete
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item_tGeometry(
        api_, req, 'delete', context['collection_id'], context['mfeature_id'],
        context['tgeometry_id'])

    assert code == HTTPStatus.NO_CONTENT
    assert response == ''
    assert rsp_headers['Content-Type'] == 'application/json'


def test_manage_collection_item_delete(
        api_, context):

    # collection not found
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item(
        api_, req, 'delete', '00000000-0000-0000-0000-000000000000',
        '00000000-0000-0000-0000-000000000000')
    assert code == HTTPStatus.NOT_FOUND

    # successful delete
    req = mock_api_request()
    rsp_headers, code, response = manage_collection_item(
        api_, req, 'delete', context['collection_id'], context['mfeature_id'])
    assert code == HTTPStatus.NO_CONTENT
    assert response == ''
    assert rsp_headers['Content-Type'] == 'application/json'

    # check feature
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    result = pmdb_provider.get_feature(context.get('collection_id'),
                                       context.get('mfeature_id'))
    assert len(result) == 0


def test_manage_collection_delete(
        api_,
        context):

    # successful delete
    req = mock_api_request()
    rsp_headers, code, response = manage_collection(
        api_, req, 'delete', context['collection_id'])
    assert code == HTTPStatus.NO_CONTENT
    assert response == ''
    assert rsp_headers['Content-Type'] == 'application/json'

    # check collection
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    result = pmdb_provider.get_collection(context.get('collection_id'))
    assert len(result) == 0
