from pygeoapi.provider.postgresql_indoordb import PostgresIndoorDB
import pytest


@pytest.fixture(scope="session")
def context():
    return {}


@pytest.fixture()
def collection_property():
    return {
        "id": "aist_waterfront_lab",
        "title": "AIST Waterfront Lab IndoorGML",
        "description": "Experimental IndoorGML data for AIST project",
        "itemType": "indoorfeature"
    }


@pytest.fixture()
def update_collection_property():
    return {
    
}


@pytest.fixture()
def indoorfeature():
    return {
  "featureType": "IndoorFeatures",
  "id": "AIST_Waterfront_Center",
  "layers": [
    {
      "id": "TL-1",
      "featureType": "ThematicLayer",
      "semanticExtension": false,
      "theme": "Physical",
      "primalSpace": {
        "id": "PS-1",
        "featureType": "PrimalSpaceLayer",
        "creationDatetime": "2025-10-30T13:00:00",
        "cellSpaceMember": [
          {
            "id": "C1",
            "featureType": "CellSpace",
            "duality": "TL-1:DS-1:N1",
            "poi": false,
            "level": "1",
            "cellSpaceGeom": {
              "geometry2D": {
                "type": "Polygon",
                "coordinates": [[[0,0], [2,0], [2,2], [0,2], [0,0]]]
              }
            },
            "boundedBy": ["TL-1:PS-1:B1"]
          },
          {
            "id": "C2",
            "featureType": "CellSpace",
            "duality": "TL-1:DS-1:N2",
            "poi": false,
            "level": "1",
            "cellSpaceGeom": {
              "geometry2D": {
                "type": "Polygon",
                "coordinates": [[[2,0], [4,0], [4,2], [2,2], [2,0]]]
              }
            },
            "boundedBy": ["TL-1:PS-1:B1"]
          }
        ],
        "cellBoundaryMember": [
          {
            "id": "B1",
            "featureType": "CellBoundary",
            "isVirtual": false,
            "duality": "TL-1:DS-1:E1",
            "cellBoundaryGeom": {
              "type": "LineString",
              "coordinates": [[2,0],[2,2]]
            }
          }
        ]
      },
      "dualSpace": {
        "id": "DS-1",
        "featureType": "DualSpaceLayer",
        "creationDatetime": "2025-10-30T13:00:00",
        "isLogical": false,
        "isDirected": false,
        "nodeMember": [
          {
            "id": "N1",
            "featureType": "Node",
            "duality": "TL-1:PS-1:C1",
            "geometry": {
              "type": "Point",
              "coordinates": [1,1]
            },
            "connects": ["TL-1:DS-1:E1"]
          },
          {
            "id": "N2",
            "featureType": "Node",
            "duality": "TL-1:PS-1:C2",
            "geometry": {
              "type": "Point",
              "coordinates": [3,1]
            },
            "connects": ["TL-1:DS-1:E1"]
          }
        ],
        "edgeMember": [
          {
            "id": "E1",
            "featureType": "Edge",
            "duality": "B1",
            "weight": 1.0,
            "geometry": {
              "type": "LineString",
              "coordinates": [[1,1],[3,1]]
            },
            "connects": [
              "TL-1:DS-1:N1",
              "TL-1:DS-1:N2"
            ]
          }
        ]
      }
    }
  ]
}


@pytest.fixture()
def thematiclayer():
    return {
    "id": "layer-indoor-nav-f1",
    "featureType": "ThematicLayer",
    "semanticExtension": true,
    "theme": "Virtual",
    "primalSpace": {
        "id": "primal-space-f1",
        "featureType": "PrimalSpaceLayer",
        "creationDatetime": "2024-01-16T15:00:00Z",
        "cellSpaceMember": [
        {
            "id": "cell-room-101",
            "featureType": "CellSpace",
            "cellSpaceName": "Server Room",
            "level": "1F",
            "poi": true,
            "duality": "node-101",
            "cellSpaceGeom": {
            "geometry2D": {
                "type": "Polygon",
                "coordinates": [
                [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
                ]
            }
            },
            "boundedBy": ["boundary-wall-01"]
        },
        {
            "id": "cell-corridor-100",
            "featureType": "CellSpace",
            "cellSpaceName": "Main Corridor",
            "level": "1F",
            "poi": false,
            "duality": "node-100",
            "cellSpaceGeom": {
            "geometry2D": {
                "type": "Polygon",
                "coordinates": [
                [[10, 0], [20, 0], [20, 10], [10, 10], [10, 0]]
                ]
            }
            }
        }
        ],
        "cellBoundaryMember": [
        {
            "id": "boundary-wall-01",
            "featureType": "CellBoundary",
            "isVirtual": true,
            "duality": "edge-101-100",
            "cellBoundaryGeom": {
            "geometry2D": {
                "type": "LineString",
                "coordinates": [[10, 2], [10, 8]]
            }
            }
        }
        ]
    },
    "dualSpace": {
        "id": "dual-space-f1",
        "featureType": "DualSpaceLayer",
        "isLogical": true,
        "isDirected": true,
        "nodeMember": [
        {
            "id": "node-101",
            "featureType": "Node",
            "duality": "cell-room-101",
            "geometry": {
            "type": "Point",
            "coordinates": [5, 5]
            },
            "connects": ["edge-101-100"]
        },
        {
            "id": "node-100",
            "featureType": "Node",
            "duality": "cell-corridor-100",
            "geometry": {
            "type": "Point",
            "coordinates": [15, 5]
            },
            "connects": ["edge-101-100"]
        }
        ],
        "edgeMember": [
        {
            "id": "edge-101-100",
            "featureType": "Edge",
            "weight": 1.5,
            "duality": "boundary-wall-01",
            "connects": ["node-101", "node-100"],
            "geometry": {
            "type": "LineString",
            "coordinates": [[5, 5], [15, 5]]
            }
        }
        ]
    }
}

@pytest.fixture()
def interlayerconnection():
    return {
  "featureType": "InterLayerConnection",
  "id": "conn_01",
  "connectedLayers": [
    "TL-1",
    "layer-indoor-nav-f1"
  ],
  "typeOfTopoExpression": "equals",
  "connectedNodes": [
    "N1",
    "node-101"
  ],
  "comment": "Connecting physical node N1 to virtual node 101"
}


@pytest.fixture()
def cellspace():
    return {
    "featureType": "CellSpace",
    "id": "cell-office-102",
    "cellSpaceName": "Office 102",
    "level": "1F",
    "poi": false,
    "duality": null,
    "boundedBy": ["B5"],
    "cellSpaceGeom": {
        "geometry2D": {
            "type": "Polygon",
            "coordinates": [[
                [20, 0],
                [30, 0],
                [30, 10],
                [20, 10],
                [20, 0]
            ]]
        },
        "geometry3D": {}
    }
}

@pytest.fixture()
def cellboundary():
    return {
    "featureType": "CellBoundary",
    "id": "boundary-wall-02",
    "isVirtual": true,
    "duality": "T1",
    "externalReference": {
        "source": "Manual_Input",
        "description": "Wall between corridor and new office"
    },
    "cellBoundaryGeom": {
        "geometry2D": {
            "type": "LineString",
            "coordinates": [
                [20, 0],
                [20, 10]
            ]
        },
        "geometry3D": {}
    }
}

@pytest.fixture()
def node():
    return {
    "featureType": "Node",
    "id": "node-corridor",
    "duality": "cell-office-102",
    "geometry": {
        "type": "Point",
        "coordinates": [15, 5]
    }
}

@pytest.fixture()
def edge():
    return {
    "featureType": "Edge",
    "id": "edge-101-100",
    "connects": [
        "node-101", 
        "node-100"
    ],
    "weight": 1.5,
    "geometry": {
        "type": "LineString",
        "coordinates": [
            [5, 5], 
            [15, 5]
        ]
    }
}

def test_query_post_collection(context, collection_property):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    collection_id = pidb_provider.post_collection(collection_property)

    assert collection_id is not None
    context['collection_id'] = collection_id


def test_query_post_indoorfeature(context, movingfeature):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    ifeature_id = \
        pidb_provider.post_indoorfeature(context.get('collection_id'),
                                         indoorfeature)

    assert ifeature_id is not None
    context['ifeature_id'] = ifeature_id


def test_query_post_thematiclayer(context, thematiclayer):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    layer_id = \
        pidb_provider.post_thematic_layer(context.get('collection_id'),
                                            context.get('ifeature_id'),
                                            thematiclayer)

    assert layer_id is not None
    context['layer_id'] = layer_id


def test_query_post_interlayerconnection(context, interlayerconnection):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    conn_id = \
    pidb_provider.post_interlayer_connection(context.get('collection_id'),
                                        context.get('ifeature_id'),
                                        interlayerconnection)
 
    assert conn_id is not None
    context['conn_id'] = conn_id


def test_query_post_cellspace(context, cellspace):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    cell_space_id = pidb_provider.post_primal_member(context.get('collection_id'),
                                                 context.get('ifeature_id'),
                                                 context.get('layer_id'),
                                                 cellspace)

    assert cell_space_id is not None
    context['cell_space_id'] = cell_space_id

def test_query_post_cellboundary(context, cellboundary):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    cell_boundary_id = pidb_provider.post_primal_member(context.get('collection_id'),
                                                 context.get('ifeature_id'),
                                                 context.get('layer_id'),
                                                 cellboundary)

    assert cell_boundary_id is not None
    context['cell_boundary_id'] = cell_boundary_id

def test_query_post_node(context, node):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    node_id = pidb_provider.post_dual_member(context.get('collection_id'),
                                                 context.get('ifeature_id'),
                                                 context.get('layer_id'),
                                                 node)

    assert node_id is not None
    context['node_id'] = node_id

def test_query_post_edge(context, edge):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    edge_id = pidb_provider.post_dual_member(context.get('collection_id'),
                                                 context.get('ifeature_id'),
                                                 context.get('layer_id'),
                                                 edge)

    assert edge_id is not None
    context['edge_id'] = edge_id

def test_query_get_collections_list():
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    result = pidb_provider.get_collections_list()

    assert result
    assert len(result) > 0
    collection = result[0]
    l_collection_id = collection[0]
    itemType = collection[2]
    assert l_collection_id is not None
    assert itemType is not None

def test_query_get_collection(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    result = pidb_provider.get_collection(context.get('collection_id'))

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

def test_query_is_indoor_collection(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    result = pidb_provider.is_indoor_collection(context.get('collection_id')) 

    assert result
    
def test_query_get_features_list():
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
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

def test_query_put_collection(context, update_collection_property):
    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    pmdb_provider.put_collection(context.get('collection_id'),
                                 update_collection_property)

    result = pmdb_provider.get_collection(context.get('collection_id'))
    collection = result[0]
    assert collection[1].get('description') == 'test_update'

def test_query_delete_temporalvalue(context):
    restriction = "AND tvalue_id ='{0}'".format(
        context.get('tvalue_id'))

    pmdb_provider = PostgresMobilityDB()
    pmdb_provider.connect()
    pmdb_provider.delete_temporalvalue(restriction)

    assert True


def test_query_delete_temporalproperties(context):
    restriction = """AND collection_id ='{0}' AND mfeature_id ='{1}'
                AND tproperties_name ='{2}'""".format(
        context.get('collection_id'),
        context.get('mfeature_id'),
        context.get('tProperties_name'))

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