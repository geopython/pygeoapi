from pygeoapi.provider.postgresql_indoordb import PostgresIndoorDB
import pytest
import json


@pytest.fixture(scope="session")
def context():
    return {}

@pytest.fixture()
def collection_property():
    raw_json = """
    {
        "id": "aist_waterfront_lab",
        "title": "AIST Waterfront Lab IndoorGML",
        "description": "Experimental IndoorGML data for AIST project",
        "itemType": "indoorfeature"
    }
    """
    return json.loads(raw_json)

@pytest.fixture()
def indoorfeature():
    raw_json = """
{
  "featureType": "IndoorFeatures",
  "id": "AIST_Waterfront_Center",
  "layers": [
    {
      "id": "TL-1",
      "featureType": "ThematicLayer",
      "semanticExtension": "false",
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
            "poi": true,
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
"""
    return json.loads(raw_json)

@pytest.fixture()
def thematiclayer():
    raw_json = """
{
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
        },
        {
            "id": "boundary-wall-03",
            "featureType": "CellBoundary",
            "isVirtual": true,
            "duality": null,
            "cellBoundaryGeom": {
            "geometry2D": {
                "type": "LineString",
                "coordinates": [[10, 5], [10, 10]]
                }
            }
        },
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
"""
    return json.loads(raw_json)

@pytest.fixture()
def interlayerconnection():
    raw_json = """
{
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
"""
    return json.loads(raw_json)

@pytest.fixture()
def cellspace():
    raw_json = """
{
    "featureType": "CellSpace",
    "id": "cell-office-102",
    "cellSpaceName": "Office 102",
    "level": "1F",
    "poi": false,
    "duality": null,
    "boundedBy": ["boundary-wall-02"],
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
"""
    return json.loads(raw_json)

@pytest.fixture()
def cellboundary():
    raw_json = """
{
    "featureType": "CellBoundary",
    "id": "boundary-wall-02",
    "isVirtual": true,
    "duality": null,
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
"""
    return json.loads(raw_json)

@pytest.fixture()
def node():
    raw_json = """
{
    "featureType": "Node",
    "id": "node-corridor",
    "duality": "cell-office-102",
    "geometry": {
        "type": "Point",
        "coordinates": [15, 5]
    }
}
"""
    return json.loads(raw_json)

@pytest.fixture()
def edge():
    raw_json = """
{
    "featureType": "Edge",
    "id": "edge-101-200",
    "connects": [
        "node-corridor",
        "node-101"
    ],
    "weight": 1.5,
    "duality": "boundary-wall-02",
    "geometry": {
        "type": "LineString",
        "coordinates": [
            [5, 5], 
            [15, 5]
        ]
    }
}
"""
    return json.loads(raw_json)

@pytest.fixture()
def update_cellspace_property():
    raw_json = """
{
    "cellSpaceName": "Executive Office 102",
    "poi": true,
    "boundedBy": [
        "boundary-wall-02",
        "boundary-wall-03"
    ]
}
"""
    return json.loads(raw_json)

@pytest.fixture()
def update_edge_property():
    raw_json = """
{
    "weight": 10.0
}
"""
    return json.loads(raw_json)

def test_query_post_collection(context, collection_property):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    collection_id = pidb_provider.post_collection(collection_property)

    assert collection_id is not None
    context['collection_id'] = collection_id


def test_query_post_indoorfeature(context, indoorfeature):
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

def test_query_post_cellboundary(context, cellboundary):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    cell_boundary_id = pidb_provider.post_primal_member(context.get('collection_id'),
                                                 context.get('ifeature_id'),
                                                 context.get('layer_id'),
                                                 cellboundary)

    assert cell_boundary_id is not None
    context['cell_boundary_id'] = cell_boundary_id

def test_query_post_cellspace(context, cellspace):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    cell_space_id = pidb_provider.post_primal_member(context.get('collection_id'),
                                                 context.get('ifeature_id'),
                                                 context.get('layer_id'),
                                                 cellspace)

    assert cell_space_id is not None
    context['cell_space_id'] = cell_space_id

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

def test_query_get_collection_items(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    bbox = [1,1,1,1]
    result, num_matched = pidb_provider.get_collection_items(context.get('collection_id'), bbox=bbox)

    assert result
    assert num_matched
    ifeature = result[0]
    assert ifeature is not None
    f_type = ifeature[0]
    assert f_type is not None
    f_id = ifeature[1]
    assert f_id is not None
    f_geom = ifeature[2]
    assert f_geom is not None
    f_props = ifeature[3]
    assert f_props is not None

def test_query_get_feature(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    bbox = [1,1,1,1]
    level = "1F"
    result = pidb_provider.get_feature(context.get('collection_id'),
                                       context.get('ifeature_id'),
                                       bbox=bbox,
                                       level=level)
    assert result
    meta_type = result[0]
    assert meta_type is not None
    meta_id = result[1]
    assert meta_id is not None
    meta_geom = result[2]
    assert meta_geom is not None
    meta_props = result[3]
    assert meta_props is not None   
    ifeature = result[4]
    assert ifeature is not None
    f_type = ifeature[0]
    assert f_type is not None
    layers = ifeature[1]
    assert layers is not None
     
def test_query_get_layer(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    bbox = [0,0,2,2]
    level = "1F"
    result_meta = pidb_provider.get_layer(context.get('collection_id'),
                                            context.get('ifeature_id'),
                                            context.get('layer_id')
                                            )
    assert result_meta
    meta_id = result_meta[0]
    assert meta_id is not None
    meta_type = result_meta[1]
    assert meta_type is not None
    meta_theme = result_meta[2]
    assert meta_theme is not None
    meta_ext = result_meta[3]
    assert meta_ext is not None
    meta_summary = result_meta[4]
    assert meta_summary is not None
    meta_bbox = result_meta[5]
    assert meta_bbox is not None

    result = pidb_provider.get_layer(context.get('collection_id'),
                                       context.get('ifeature_id'),
                                       context.get('layer_id'),
                                       level=level,
                                       bbox=bbox)
    assert result
    t_id = result[0]
    assert t_id is not None
    t_type = result[1]
    assert t_type is not None
    t_theme = result[2]
    assert t_theme is not None
    t_ext = result[3]
    assert t_ext is not None    
    t_primal = result[4]
    assert t_primal is not None
    t_dual = result[5]
    assert t_dual is not None

def test_query_get_layers(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    theme = "physical"
    level = "1F"
    result = pidb_provider.get_layers(context.get('collection_id'),
                                       context.get('ifeature_id'),
                                       level=level,
                                       theme=theme)
    assert result
    lvl = result[0]
    assert lvl is not None
    layers = result[1]
    assert layers is not None    

def test_query_get_interlayer_connections(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    topo_type = "equals"
    result = pidb_provider.get_interlayer_connections(context.get('collection_id'),
                                                      context.get('ifeature_id'),
                                                      connected_layer_id=context.get('layer_id'),
                                                      topo_type=topo_type)
    assert result
    conn = result[0]
    assert conn
    conn_id = conn[0]
    assert conn_id is not None
    conn_type = conn[1]
    assert conn_type is not None
    conn_topo= conn[2]
    assert conn_topo is not None
    conn_layers = conn[3]
    assert conn_layers is not None

def test_query_get_primal_members(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    level = "1F"
    poi = "true"
    result = pidb_provider.get_primal_members(context.get('collection_id'),
                                            context.get('ifeature_id'),
                                            context.get('layer_id'),
                                            level=level,
                                            poi=poi)    
    assert result
    t_id = result[0]
    assert t_id is not None
    p_type = result[1]
    assert p_type is not None
    p_create = result[2]
    assert p_create is not None
    space_mem = result[4]
    assert space_mem is not None
    boundary_mem = result[5]
    assert boundary_mem is not None
    cell = space_mem[0]
    assert cell is not None
    boundary = boundary_mem[0]
    assert boundary is not None

def test_query_get_primal_member(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    cell = pidb_provider.get_primal_member(context.get('collection_id'),
                                            context.get('ifeature_id'),
                                            context.get('layer_id'),
                                            context.get('cell_space_id'))
    assert cell
    cid = cell[0]
    assert cid is not None
    c_type = cell[1]
    assert c_type is not None
    c_name = cell[2]
    assert c_name is not None
    lvl = cell[3]
    assert lvl is not None
    poi = cell[4]
    assert poi is not None
    c_duality = cell[5]
    assert c_duality is not None
    c_geom = cell[6]
    assert c_geom is not None
    bounded_by = cell[8]
    assert bounded_by is not None

    boundary = pidb_provider.get_primal_member(context.get('collection_id'),
                                            context.get('ifeature_id'),
                                            context.get('layer_id'),
                                            context.get('cell_boundary_id'))
    assert boundary
    bid = boundary[0]
    assert bid is not None
    b_type = boundary[1]
    assert b_type is not None
    is_virtual = boundary[2]
    assert is_virtual is not None
    b_duality = boundary[3]
    assert b_duality is not None
    b_geom = boundary[4]
    assert b_geom is not None

def test_query_dual_members(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    minWeight = 1.0
    maxWeight = 2.5
    results = pidb_provider.get_dual_members(context.get('collection_id'),
                                             context.get('ifeature_id'),
                                             context.get('layer_id'),
                                             min_weight=minWeight,
                                             max_weight=maxWeight)
    assert results
    d_id = results[0]
    assert d_id is not None
    d_type = results[1]
    assert d_type is not None
    d_logical = results[2]
    assert d_logical is not None
    d_directed = results[3]
    assert d_directed is not None
    node_mem = results[6]
    assert node_mem is not None
    edge_mem = results[7]
    assert edge_mem is not None

def test_query_get_dual_member(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    node = pidb_provider.get_dual_member(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('node_id'))
    assert node
    n_id = node[0]
    assert n_id is not None
    n_type = node[1]
    assert n_type is not None
    n_geom = node[2]
    assert n_geom is not None
    n_dual = node[3]
    assert n_dual is not None
    n_connect = node[4]
    assert n_connect is not None

    edge = pidb_provider.get_dual_member(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('edge_id'))
    
    assert edge
    e_id = edge[0]
    assert e_id is not None
    e_type = edge[1]
    assert e_type is not None
    e_geom = edge[2]
    assert e_geom is not None
    e_dual = edge[3]
    assert e_dual is not None
    e_weight = edge[4]
    assert e_weight is not None
    e_connect = edge[5]
    assert e_connect is not None

def test_query_geometric_query(context):
    geometry = "POINT(10 10)"
    op = "intersects"
    level = "1F"
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    result = pidb_provider.geometric_query(context.get('collection_id'),
                                           context.get('ifeature_id'),
                                           context.get('layer_id'),
                                           op=op,
                                           geometry=geometry,
                                           level=level)
    assert result
    t_id = result[0]
    assert t_id is not None
    t_primal = result[4]
    assert t_primal is not None
    t_dual = result[5]
    assert t_dual is not None

def test_query_routing_query(context):
    sn = "node-corridor"
    dn = "node-100"
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    result = pidb_provider.routing_query(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         sn=sn,
                                         dn=dn)
    assert result
    r_type = result[0]
    assert r_type is not None
    r_sn = result[1]
    assert r_sn is not None
    r_dn = result[2]
    assert r_dn is not None
    r_cost = result[3]
    assert r_cost is not None
    r_path = result[4]
    assert r_path is not None
    p_seq1 = r_path[0]
    assert p_seq1 is not None

def test_query_bounding_cell_space(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    result = pidb_provider.routing_query(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('cell_boundary_id'))
    assert result
    c_id = result[0]
    assert c_id is not None
    c_level = result[3]
    assert c_level is not None
    c_poi = result[4]
    assert c_poi is not None
    c_geom = result[6]
    assert c_geom is not None
    c_bounded = result[8]
    assert c_bounded is not None

def test_query_connected_nodes(context):
    hop = 1
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    result = pidb_provider.connected_nodes(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('node_id'),
                                         hop=hop)
    assert result
    r_type = result[0]
    assert r_type is not None
    sn = result[1]
    assert sn is not None
    connected = result[2]
    assert connected is not None
    n1 = connected[0]
    assert n1 is not None

def test_query_patch_primal_member(context, update_cellspace_property):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    success = pidb_provider.patch_cell_space(context.get('collection_id'),
                                            context.get('ifeature_id'),
                                            context.get('layer_id'),
                                            context.get('cell_space_id'),
                                            data=update_cellspace_property)
    assert success
    result = pidb_provider.get_primal_member(context.get('collection_id'),
                                            context.get('ifeature_id'),
                                            context.get('layer_id'),
                                            context.get('cell_space_id'))
    r_bounded = result[8]
    assert result.get('cellSpaceName') == 'Executive Office 102'
    assert result.get('poi') == 'true'
    assert len(r_bounded) == 2

def test_query_patch_edge(context, update_edge_property):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    success = pidb_provider.patch_edge(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('edge_id'),
                                         data=update_edge_property)
    assert success
    result = pidb_provider.get_dual_member(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('edge_id'))
    assert result.get('weight') == '10.0'

def test_query_delete_dual_member(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    success = pidb_provider.delete_dual_member(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('node_id'))
    assert success
    result_e = pidb_provider.get_dual_member(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('edge_id'))
    assert result_e is None
    result_n = pidb_provider.get_dual_member(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('node_id'))
    assert result_n is None

def test_query_delete_primal_member(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    success_b = pidb_provider.delete_primal_member(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('cell_boundary_id'))
    assert success_b
    result_b = pidb_provider.get_primal_member(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('cell_boundary_id'))
    assert result_b is None
    success_c = pidb_provider.delete_primal_member(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('cell_space_id'))
    assert success_c
    result_c = pidb_provider.get_primal_member(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('cell_space_id'))
    assert result_c is None

def test_query_delete_interlayer_connection(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    success = pidb_provider.delete_interlayer_connection(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('conn_id'))
    assert success
    result = pidb_provider.get_interlayer_connections(context.get('collection_id'),
                                          context.get('ifeature_id'))
    assert len(result) == 0

def test_query_delete_thematic_layer(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    success = pidb_provider.delete_thematic_layer(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'))
    assert success
    result = pidb_provider.get_layer(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'))
    assert result is None

def test_query_delete_indoorfeature(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    success = pidb_provider.delete_indoorfeature(context.get('collection_id'),
                                                context.get('ifeature_id'))
    assert success
    result = pidb_provider.get_feature(context.get('collection_id'),
                                          context.get('ifeature_id'))
    assert result is None
    
def test_query_delete_collection(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    success = pidb_provider.delete_collection(context.get('collection_id'))    
    assert success
    result = pidb_provider.get_collection(context.get('collection_id'))
    assert result is None
    