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
        "id": "test_collection",
        "title": "test_collection for test api",
        "description": "test sample indoorfeature collection data",
        "itemType": "indoorfeature"
    }
    """
    return json.loads(raw_json)

@pytest.fixture()
def indoorfeature():
    raw_json = """
{
  "featureType": "IndoorFeatures",
  "id": "test_indoorfeature",
  "geometry": {
    "type": "Point",
    "coordinates": [
        1, 1
    ]
  },
  "properties": {},
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
    "id": "layer-f1",
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
    "layer-f1"
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
    l_collection_id = collection['id']
    itemType = collection['itemType']
    assert l_collection_id is not None
    assert itemType is not None

def test_query_get_collection(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    result = pidb_provider.get_collection(context.get('collection_id'))

    assert result
    collection_id = result['id']
    assert collection_id is not None
    collection_type = result['itemType']
    assert collection_type is not None
    col_title = result['title']
    assert col_title is not None
    col_desc = result['description']
    assert col_desc is not None

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
    f_type = ifeature['type']
    assert f_type is not None
    f_id = ifeature['id']
    assert f_id is not None
    f_geom = ifeature['geometry']
    assert f_geom is not None
    f_props = ifeature['properties']
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
    meta_type = result['type']
    assert meta_type is not None
    meta_id = result['id']
    assert meta_id is not None
    meta_geom = result['geometry']
    assert meta_geom is not None
    meta_props = result['properties']
    assert meta_props is not None   
    ifeature = result['IndoorFeatures']
    assert ifeature is not None
    f_type = ifeature['featureType']
    assert f_type is not None
    layers = ifeature['layers']
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
    meta_id = result_meta['id']
    assert meta_id is not None
    meta_type = result_meta['featureType']
    assert meta_type is not None
    meta_theme = result_meta['theme']
    assert meta_theme is not None
    meta_ext = result_meta['semanticExtension']
    assert meta_ext is not None
    meta_summary = result_meta['summary']
    assert meta_summary is not None
    meta_bbox = result_meta['bbox']
    assert meta_bbox is not None

    result = pidb_provider.get_layer(context.get('collection_id'),
                                       context.get('ifeature_id'),
                                       context.get('layer_id'),
                                       level=level,
                                       bbox=bbox)
    assert result
    t_id = result['id']
    assert t_id is not None
    t_type = result['featureType']
    assert t_type is not None
    t_theme = result['theme']
    assert t_theme is not None
    t_ext = result['semanticExtension']
    assert t_ext is not None    
    t_primal = result['primalSpace']
    assert t_primal is not None
    t_dual = result['dualSpace']
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
    lvl = result['levels']
    assert lvl is not None
    layers = result['layers']
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
    li_of_connections = result['layerConnections']
    assert li_of_connections is not None
    conn = li_of_connections[0]
    conn_id = conn['id']
    assert conn_id is not None
    conn_type = conn['featureType']
    assert conn_type is not None
    conn_topo= conn['typeOfTopoExpression']
    assert conn_topo is not None
    conn_layers = conn['connectedLayers']
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
    t_id = result['id']
    assert t_id is not None
    p_type = result['featureType']
    assert p_type is not None
    p_create = result['creationDatetime']
    assert p_create is not None
    space_mem = result['cellSpaceMember']
    assert space_mem is not None
    boundary_mem = result['cellBoundaryMember']
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
    cid = cell['id']
    assert cid is not None
    c_type = cell['featureType']
    assert c_type is not None
    c_name = cell['cellSpaceName']
    assert c_name is not None
    lvl = cell['level']
    assert lvl is not None
    poi = cell['poi']
    assert poi is not None
    c_duality = cell['duality']
    assert c_duality is not None
    c_geom = cell['cellSpaceGeom']
    assert c_geom is not None
    bounded_by = cell['boundedBy']
    assert bounded_by is not None

    boundary = pidb_provider.get_primal_member(context.get('collection_id'),
                                            context.get('ifeature_id'),
                                            context.get('layer_id'),
                                            context.get('cell_boundary_id'))
    assert boundary
    bid = boundary['id']
    assert bid is not None
    b_type = boundary['featureType']
    assert b_type is not None
    is_virtual = boundary['isVirtual']
    assert is_virtual is not None
    b_duality = boundary['duality']
    assert b_duality is not None
    b_geom = boundary['cellBoundaryGeom']
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
    d_id = results['id']
    assert d_id is not None
    d_type = results['featureType']
    assert d_type is not None
    d_logical = results['isLogical']
    assert d_logical is not None
    d_directed = results['isDirected']
    assert d_directed is not None
    node_mem = results['nodeMember']
    assert node_mem is not None
    edge_mem = results['edgeMember']
    assert edge_mem is not None

def test_query_get_dual_member(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    node = pidb_provider.get_dual_member(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('node_id'))
    assert node
    n_id = node['id']
    assert n_id is not None
    n_type = node['featureType']
    assert n_type is not None
    n_geom = node['geometry']
    assert n_geom is not None
    n_dual = node['duality']
    assert n_dual is not None
    n_connect = node['connects']
    assert n_connect is not None

    edge = pidb_provider.get_dual_member(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('edge_id'))
    
    assert edge
    e_id = edge['id']
    assert e_id is not None
    e_type = edge['featureType']
    assert e_type is not None
    e_geom = edge['geometry']
    assert e_geom is not None
    e_dual = edge['duality']
    assert e_dual is not None
    e_weight = edge['weight']
    assert e_weight is not None
    e_connect = edge['connects']
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
    t_id = result['id']
    assert t_id is not None
    t_primal = result['primalSpace']
    assert t_primal is not None
    t_dual = result['dualSpace']
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
    r_type = result['type']
    assert r_type is not None
    r_sn = result['start_node']
    assert r_sn is not None
    r_dn = result['destination_node']
    assert r_dn is not None
    r_cost = result['cost']
    assert r_cost is not None
    r_path = result['path_segments']
    assert r_path is not None
    p_seq1 = r_path[0]
    assert p_seq1 is not None

def test_query_bounding_cell_space(context):
    pidb_provider = PostgresIndoorDB()
    pidb_provider.connect()
    result = pidb_provider.bounding_cell_space(context.get('collection_id'),
                                         context.get('ifeature_id'),
                                         context.get('layer_id'),
                                         context.get('cell_boundary_id'))
    assert result
    c_id = result['id']
    assert c_id is not None
    c_level = result['level']
    assert c_level is not None
    c_poi = result['poi']
    assert c_poi is not None
    c_geom = result['cellSpaceGeom']
    assert c_geom is not None
    c_bounded = result['boundedBy']
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
    r_type = result['type']
    assert r_type is not None
    sn = result['start_node']
    assert sn is not None
    connected = result['connected_nodes']
    assert connected is not None
    n1 = connected[0]
    assert n1 is not None

def test_query_patch_cell_space(context, update_cellspace_property):
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
    r_bounded = result['boundedBy']
    assert result.get('cellSpaceName') == 'Executive Office 102'
    assert result.get('poi') == True
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
    assert float(result['weight']) == 10.0

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
    