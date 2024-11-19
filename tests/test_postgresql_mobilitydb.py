from pygeoapi.provider.postgresql_mobilitydb import PostgresMobilityDB
import pytest


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


def test_query_post_collection(context, collection_property):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    collection_id = pmdb_provider.post_collection(collection_property)

    assert collection_id is not None
    context['collection_id'] = collection_id


def test_query_post_movingfeature(context, movingfeature):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    mfeature_id = \
        pmdb_provider.post_movingfeature(context.get('collection_id'),
                                         movingfeature)

    assert mfeature_id is not None
    context['mfeature_id'] = mfeature_id


def test_query_post_temporalgeometry(context, temporalgeometry):

    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    tgeometry_id = \
        pmdb_provider.post_temporalgeometry(context.get('collection_id'),
                                            context.get('mfeature_id'),
                                            temporalgeometry)

    assert tgeometry_id is not None
    context['tgeometry_id'] = tgeometry_id


def test_query_post_temporalproperties(context, temporalproperties):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    l_temporal_properties = [temporalproperties] if not isinstance(
        temporalproperties, list) else temporalproperties

    canPost = pmdb_provider.check_temporalproperty_can_post(
        context.get('collection_id'),
        context.get('mfeature_id'),
        l_temporal_properties)

    tProperty_name_list = []
    if canPost:
        for temporal_property in l_temporal_properties:
            tProperty_name_list.extend(pmdb_provider.
                                       post_temporalproperties(
                                           context.get('collection_id'),
                                           context.get('mfeature_id'),
                                           temporal_property))

    assert len(tProperty_name_list) == 4
    tProperty_name = tProperty_name_list[-1]
    assert tProperty_name is not None
    context['tProperty_name'] = tProperty_name


def test_query_post_temporalvalue(context, temporalvalue_data):

    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    pmdb_provider.post_temporalvalue(context.get('collection_id'),
                                     context.get('mfeature_id'),
                                     context.get('tProperty_name'),
                                     temporalvalue_data)

    assert True


def test_query_put_collection(context, update_collection_property):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    pmdb_provider.put_collection(context.get('collection_id'),
                                 update_collection_property)

    result = pmdb_provider.get_collection(context.get('collection_id'))
    collection = result[0]
    assert collection[1].get('description') == 'test_update'


def test_query_get_collections_list():
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    result = pmdb_provider.get_collections_list()

    assert result
    assert len(result) > 0
    collection = result[0]
    l_collection_id = collection[0]
    assert l_collection_id is not None


def test_query_get_collections():
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    result = pmdb_provider.get_collections()

    assert result
    assert len(result) > 0
    collection = result[0]
    l_collection_id = collection[0]
    assert l_collection_id is not None
    collection_property = collection[1]
    assert collection_property is not None


def test_query_get_collection(context):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    result = pmdb_provider.get_collection(context.get('collection_id'))

    assert result
    assert len(result) == 1
    collection = result[0]
    l_collection_id = collection[0]
    assert l_collection_id is not None
    collection_property = collection[1]
    assert collection_property is not None
    extentLifespan = collection[2]
    assert extentLifespan is not None
    extentTGeometry = collection[3]
    assert extentTGeometry is not None


def test_query_get_features_list():
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    result = pmdb_provider.get_features_list()

    assert result
    assert len(result) > 0
    mfeature = result[0]
    l_collection_id = mfeature[0]
    assert l_collection_id is not None
    l_mfeature_id = mfeature[1]
    assert l_mfeature_id is not None


def test_query_get_tProperties_name_list():
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    result = pmdb_provider.get_tProperties_name_list()

    assert result
    assert len(result) > 0
    tPropertie = result[0]
    l_collection_id = tPropertie[0]
    assert l_collection_id is not None
    l_mfeature_id = tPropertie[1]
    assert l_mfeature_id is not None
    tproperties_name = tPropertie[2]
    assert tproperties_name is not None


def test_query_get_features(
        context,
        bbox=[
            100,
            30,
            0,
            200,
            40,
            10],
        datetime='2011-07-14 22:01:01.000,2011-07-14 22:01:01.000',
        limit=10, offset=0, sub_trajectory=False):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    result, number_matched, number_returned = pmdb_provider.get_features(
        context.get('collection_id'), bbox, datetime, limit, offset,
        sub_trajectory)

    assert result
    assert number_matched
    assert number_returned
    assert len(result) > 0
    mfeature = result[0]
    l_collection_id = mfeature[0]
    assert l_collection_id is not None
    l_mfeature_id = mfeature[1]
    assert l_mfeature_id is not None
    mf_geometry = mfeature[2]
    assert mf_geometry is not None
    mf_property = mfeature[3]
    assert mf_property is not None
    lifespan = mfeature[4]
    assert lifespan is not None
    extent_tGeometry = mfeature[5]
    assert extent_tGeometry is not None
    extent_tProperties_value_float = mfeature[6]
    assert extent_tProperties_value_float is not None
    extent_tProperties_value_text = mfeature[7]
    assert extent_tProperties_value_text is not None


def test_query_get_feature(context):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    result = pmdb_provider.get_feature(context.get('collection_id'),
                                       context.get('mfeature_id'))

    assert result
    assert len(result) > 0
    mfeature = result[0]
    l_collection_id = mfeature[0]
    assert l_collection_id is not None
    l_mfeature_id = mfeature[1]
    assert l_mfeature_id is not None
    mf_geometry = mfeature[2]
    assert mf_geometry is not None
    mf_property = mfeature[3]
    assert mf_property is not None
    lifespan = mfeature[4]
    assert lifespan is not None
    extent_tGeometry = mfeature[5]
    assert extent_tGeometry is not None


def test_query_get_temporalgeometries(
        context,
        bbox=[
            100,
            30,
            0,
            200,
            40,
            10],
        leaf='2011-07-14 22:01:01.000',
        datetime='2011-07-14 22:01:01.000,2011-07-14 22:01:01.000',
        limit=10,
        offset=0,
        sub_trajectory=False):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    result, number_matched, number_returned = \
        pmdb_provider.get_temporalgeometries(
            context.get('collection_id'), context.get('mfeature_id'), bbox,
            leaf, datetime, limit, offset, sub_trajectory)

    assert result
    assert number_matched
    assert number_returned
    assert len(result) > 0
    tgeometry = result[0]
    l_collection_id = tgeometry[0]
    assert l_collection_id is not None
    l_mfeature_id = tgeometry[1]
    assert l_mfeature_id is not None
    tgeometry_id = tgeometry[2]
    assert tgeometry_id is not None


def test_query_get_temporalproperties(
        context,
        datetime='2011-07-14 22:01:01.450,2011-07-14 22:01:01.450',
        limit=10,
        offset=0,
        sub_temporal_value=True):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    result, number_matched, number_returned = \
        pmdb_provider.get_temporalproperties(
            context.get('collection_id'), context.get('mfeature_id'),
            datetime, limit, offset, sub_temporal_value)

    assert result
    assert number_matched
    assert number_returned
    assert len(result) > 0
    tproperties = result[0]
    l_collection_id = tproperties[0]
    assert l_collection_id is not None
    l_mfeature_id = tproperties[1]
    assert l_mfeature_id is not None
    tgeometry_id = tproperties[2]
    assert tgeometry_id is not None
    tproperty = tproperties[3]
    assert tproperty is not None


def test_query_get_temporalproperties_value(
        context,
        datetime='2011-07-16 22:01:01.450,2011-07-16 22:01:01.450',
        leaf='2011-07-16 22:01:01.450',
        sub_temporal_value=False):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    result = pmdb_provider.get_temporalproperties_value(
        context.get('collection_id'), context.get('mfeature_id'),
        context.get('tProperty_name'), datetime, leaf, sub_temporal_value)

    assert result
    assert len(result) > 0
    tpropertiesvalue = result[0]
    l_collection_id = tpropertiesvalue[0]
    assert l_collection_id is not None
    l_mfeature_id = tpropertiesvalue[1]
    assert l_mfeature_id is not None
    tgeometry_id = tpropertiesvalue[2]
    assert tgeometry_id is not None
    tproperty = tpropertiesvalue[3]
    assert tproperty is not None
    datetime_group = tpropertiesvalue[4]
    assert datetime_group is not None
    pvalue_float = tpropertiesvalue[5]
    pvalue_text = tpropertiesvalue[6]
    assert pvalue_float is not None or pvalue_text is not None


def test_query_get_velocity(context,
                            datetime='2011-07-14 22:01:01.450'):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    tProperties = pmdb_provider.get_velocity(
        context.get('collection_id'), context.get('mfeature_id'),
        context.get('tgeometry_id'), datetime)

    assert tProperties
    name = tProperties.get('name')
    assert name is not None
    type = tProperties.get('type')
    assert type is not None
    form = tProperties.get('form')
    assert form is not None
    value_sequence = tProperties.get('valueSequence')
    assert value_sequence is not None


def test_query_get_distance(context,
                            datetime='2011-07-14 22:01:01.450'):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    tProperties = pmdb_provider.get_distance(
        context.get('collection_id'), context.get('mfeature_id'),
        context.get('tgeometry_id'), datetime)

    assert tProperties
    name = tProperties.get('name')
    assert name is not None
    type = tProperties.get('type')
    assert type is not None
    form = tProperties.get('form')
    assert form is not None
    value_sequence = tProperties.get('valueSequence')
    assert value_sequence is not None


def test_query_get_acceleration(context,
                                datetime='2011-07-14 22:01:01.450'):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    tProperties = pmdb_provider.get_acceleration(
        context.get('collection_id'), context.get('mfeature_id'),
        context.get('tgeometry_id'), datetime)

    assert tProperties
    name = tProperties.get('name')
    assert name is not None
    type = tProperties.get('type')
    assert type is not None
    form = tProperties.get('form')
    assert form is not None
    value_sequence = tProperties.get('valueSequence')
    assert value_sequence is not None


def test_query_delete_temporalproperties(context):
    restriction = "AND tproperties_name ='{0}'".format(
        context.get('tProperty_name'))

    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    pmdb_provider.delete_temporalproperties(restriction)

    assert True


def test_query_delete_temporalgeometry(context):
    restriction = "AND tgeometry_id ='{0}'".format(context.get('tgeometry_id'))

    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    pmdb_provider.delete_temporalgeometry(restriction)

    assert True


def test_query_delete_movingfeature(context):
    restriction = "AND mfeature_id ='{0}'".format(context.get('mfeature_id'))

    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    pmdb_provider.delete_movingfeature(restriction)

    result = pmdb_provider.get_feature(context.get('collection_id'),
                                       context.get('mfeature_id'))
    assert len(result) == 0


def test_query_delete_collection(context):
    restriction = "AND collection_id ='{0}'".format(
        context.get('collection_id'))

    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    pmdb_provider.delete_collection(restriction)

    result = pmdb_provider.get_collection(context.get('collection_id'))
    assert len(result) == 0
