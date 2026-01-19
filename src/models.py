from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Float, Enum
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
import enum

# Define the base class for all models
Base = declarative_base()

# --- ENUMS (Must match SQL types) ---
class SpaceType(enum.Enum):
    primal = "primal"
    dual = "dual"

class CellType(enum.Enum):
    space = "space"
    boundary = "boundary"

class NodeEdgeType(enum.Enum):
    node = "node"
    edge = "edge"

# --- MODELS ---

class Collection(Base):
    __tablename__ = "collection"

    id = Column(Integer, primary_key=True)
    id_str = Column(String, unique=True)
    collection_property = Column(JSONB)

    # Relationships
    features = relationship("IndoorFeature", back_populates="collection")


class IndoorFeature(Base):
    __tablename__ = "indoorfeature"

    id = Column(Integer, primary_key=True)
    id_str = Column(String, unique=True)
    collection_id = Column(Integer, ForeignKey("collection.id"), nullable=False)
    
    # Spatial Column (SRID 4326 is standard WGS84)
    geojson_geometry = Column(Geometry(geometry_type="GEOMETRY", srid=4326))
    geojson_properties = Column(JSONB)

    # Relationships
    collection = relationship("Collection", back_populates="features")
    thematic_layers = relationship("ThematicLayer", back_populates="feature")
    cells = relationship("CellSpaceBoundary", back_populates="feature")


class ThematicLayer(Base):
    __tablename__ = "thematiclayer"

    id = Column(Integer, primary_key=True)
    id_str = Column(String, unique=True)
    space_id_str = Column(String, unique=True)
    collection_id = Column(Integer, ForeignKey("collection.id"), nullable=False)
    indoorfeature_id = Column(Integer, ForeignKey("indoorfeature.id"), nullable=False)
    
    semantic_extension = Column(Boolean, nullable=False)
    space_type = Column(Enum(SpaceType, name="spcaetype")) # Maps to SQL Enum
    creation_datetime = Column(DateTime)
    termination_datetime = Column(DateTime)
    is_logical = Column(Boolean)
    is_directed = Column(Boolean)

    feature = relationship("IndoorFeature", back_populates="thematic_layers")


class CellSpaceBoundary(Base):
    __tablename__ = "cell_space_n_boundary"

    id = Column(Integer, primary_key=True)
    id_str = Column(String, unique=True)
    type = Column(Enum(CellType, name="celltype"), nullable=False)
    collection_id = Column(Integer, ForeignKey("collection.id"), nullable=False)
    indoorfeature_id = Column(Integer, ForeignKey("indoorfeature.id"), nullable=False)
    thematiclayer_id = Column(Integer, ForeignKey("thematiclayer.id"), nullable=False)
    
    # Mapping SQL "2D_geometry" to Python "geometry_2d"
    geometry_2d = Column("2D_geometry", Geometry(geometry_type="GEOMETRY", srid=4326))
    geometry_3d = Column("3D_geometry", Geometry(geometry_type="GEOMETRY", srid=4326))
    
    cell_name = Column(String)
    duality_id = Column(Integer)
    level = Column(String)
    poi = Column(Boolean)
    is_virtual = Column(Boolean)
    external_reference = Column(JSONB)
    bounded_by_cell_id = Column(Integer)

    feature = relationship("IndoorFeature", back_populates="cells")


class NodeEdge(Base):
    __tablename__ = "node_n_edge"

    id = Column(Integer, primary_key=True)
    id_str = Column(String, unique=True)
    type = Column(Enum(NodeEdgeType, name="node_edge_type"), nullable=False)
    collection_id = Column(Integer, ForeignKey("collection.id"), nullable=False)
    indoorfeature_id = Column(Integer, ForeignKey("indoorfeature.id"), nullable=False)
    thematiclayer_id = Column(Integer, ForeignKey("thematiclayer.id"), nullable=False)
    
    geometry_val = Column(Geometry(geometry_type="GEOMETRY", srid=4326))
    duality_id = Column(Integer)
    weight = Column(Float)


class Connects(Base):
    __tablename__ = "connects"
    
    # Since this is a pure association table in your SQL (no primary key), 
    # we map it slightly differently or usually give it a composite PK.
    # For now, we treat it as a mapped table.
    node_source_id = Column(Integer, ForeignKey("node_n_edge.id"), primary_key=True)
    node_target_id = Column(Integer, ForeignKey("node_n_edge.id"), primary_key=True)
    edge_id = Column(Integer, ForeignKey("node_n_edge.id"), primary_key=True)


class InterLayerConnection(Base):
    __tablename__ = "interlayerconnection"

    id = Column(Integer, primary_key=True)
    id_str = Column(String)
    collection_id = Column(Integer, ForeignKey("collection.id"), nullable=False)
    indoorfeature_id = Column(Integer, ForeignKey("indoorfeature.id"), nullable=False)
    connected_layer_a = Column(Integer, ForeignKey("thematiclayer.id"), nullable=False)
    connected_layer_b = Column(Integer, ForeignKey("thematiclayer.id"), nullable=False)
    connected_cell_a = Column(Integer)
    connected_cell_b = Column(Integer)
    connected_node_a = Column(Integer)
    connected_node_b = Column(Integer)
    comment = Column(String)