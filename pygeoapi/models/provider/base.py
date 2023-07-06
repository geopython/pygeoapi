# ****************************** -*-
# flake8: noqa
# =================================================================
#
# Authors: Antonio Cerciello <anto.nio.cerciello@gmail.com>
#
# Copyright (c) 2022 Antonio Cerciello
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class TilesMetadataFormat(Enum):
    # Tile Set Metadata
    DEFAULT = "Tile Set Metadata"
    # TileJSON 3.0
    TILEJSON = "TileJSON"
    # Custom JSON
    CUSTOMJSON = "Custom"


# Tile Set Metadata Enums
class AccessConstraintsEnum(str, Enum):
    UNCLASSIFIED = "unclassified"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"
    SECRET = "secret"
    TOPSECRET = "topSecret"


class DataTypeEnum(str, Enum):
    MAP = "map"
    VECTOR = "vector"
    COVERAGE = "coverage"


class GeometryDimensionEnum(int, Enum):
    POINTS = 0
    CURVES = 1
    SURFACES = 2
    SOLIDS = 3


class TileMatrixSetEnumType(BaseModel):
    tileMatrixSet: str
    tileMatrixSetURI: str
    crs: str
    tileMatrixSetDefinition: dict


class TileMatrixSetEnum(Enum):
    WORLDCRS84QUAD = TileMatrixSetEnumType(
        tileMatrixSet="WorldCRS84Quad",
        tileMatrixSetURI="http://schemas.opengis.net/tms/1.0/json/examples/WorldCRS84Quad.json",  # noqa
        crs="http://www.opengis.net/def/crs/OGC/1.3/CRS84",
        tileMatrixSetDefinition=
            {
                'type': 'application/json',
                'rel': 'http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme',
                'title': 'WorldCRS84QuadTileMatrixSet definition (as JSON)',
                'href': 'https://raw.githubusercontent.com/opengeospatial/2D-Tile-Matrix-Set/master/registry/json/WorldCRS84Quad.json'  # authoritative TMS definition
            }
        )
    WEBMERCATORQUAD = TileMatrixSetEnumType(
        tileMatrixSet="WebMercatorQuad",
        tileMatrixSetURI="http://schemas.opengis.net/tms/1.0/json/examples/WebMercatorQuad.json",  # noqa
        crs="http://www.opengis.net/def/crs/EPSG/0/3857",
        tileMatrixSetDefinition=
            {
                'type': 'application/json',
                'rel': 'http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme',
                'title': 'WebMercatorQuadTileMatrixSet definition (as JSON)',
                'href': 'https://raw.githubusercontent.com/opengeospatial/2D-Tile-Matrix-Set/master/registry/json/WebMercatorQuad.json'  # authoritative TMS definition
            }
        )


# Tile Set Metadata Sub Types
class TileMatrixLimitsType(BaseModel):
    tileMatrix: str
    minTileRow: int
    maxTileRow: int
    minTileCol: int
    maxTileCol: int


class TwoDBoundingBoxType(BaseModel):
    lowerLeft: List[float]
    upperRight: List[float]
    crs: Optional[str]


class LinkType(BaseModel):
    href: str
    rel: Optional[str]
    type_: Optional[str]
    hreflang: Optional[str]
    title: Optional[str]
    length: Optional[int]


class GeospatialDataType(BaseModel):
    id: Optional[str]
    title: Optional[str] = None
    description: Optional[str]
    keywords: Optional[List[str]]
    dataType: DataTypeEnum = DataTypeEnum.VECTOR
    geometryDimension: Optional[GeometryDimensionEnum]
    maxTileMatrix: Optional[str]
    minTileMatrix: Optional[str]
    minScaleDenominator: Optional[float]
    maxScaleDenominator: Optional[float]
    minCellSize: Optional[float]
    maxCellSize: Optional[float]
    boundingBox: Optional[TwoDBoundingBoxType]
    links: Optional[LinkType]
    propertiesSchema: Optional[dict]


class StyleType(BaseModel):
    id: Optional[str]
    title: Optional[str]
    description: Optional[str]
    keywords: Optional[List[str]]
    links: Optional[LinkType]


class TilePointType(BaseModel):
    crs: str
    coordinates: Optional[List[float]]
    scaleDenominator: Optional[float]
    cellSize: Optional[float]
    # CodeType as adaptation of MD_Identifier class ISO 19115
    tileMatrix: str
    cellSize: Optional[str]


class TileSetMetadata(BaseModel):
    # A title for this tileset
    title: Optional[str]
    # Brief narrative description of this tile set
    description: Optional[str]
    # keywords about this tileset
    keywords: Optional[List[str]]
    # Version of the Tile Set. Changes if the data behind the tiles
    # has been changed
    version: Optional[str]
    # Useful information to contact the authors or custodians for the Tile Set
    pointOfContact: Optional[str]
    # Short reference to recognize the author or provider
    attribution: Optional[str]
    # License applicable to the tiles
    license_: Optional[str]
    # Restrictions on the availability of the Tile Set that the user needs to
    # be aware of before using or redistributing the Tile Set
    accessConstraints: Optional[AccessConstraintsEnum] = AccessConstraintsEnum.UNCLASSIFIED
    # Media types available for the tiles
    mediaTypes:  Optional[List[str]]
    # Type of data represented in the tileset
    dataType: DataTypeEnum = DataTypeEnum.VECTOR
    # Limits for the TileRow and TileCol values for each TileMatrix in the
    # tileMatrixSet. If missing, there are no limits other that the ones
    # imposed by the TileMatrixSet. If present the TileMatrices listed are
    # limited and the rest not available at all
    tileMatrixSetLimits: Optional[TileMatrixLimitsType]
    # Coordinate Reference System (CRS)
    crs: Optional[str]
    # Epoch of the Coordinate Reference System (CRS)
    epoch: Optional[int]
    # Minimum bounding rectangle surrounding the tile matrix set, in the
    # supported CRS
    boundingBox: Optional[TwoDBoundingBoxType]
    # When the Tile Set was first produced
    created: Optional[datetime]
    # Last Tile Set change/revision
    updated: Optional[datetime]
    layers: Optional[GeospatialDataType]
    # Style involving all layers used to generate the tileset
    style: Optional[StyleType]
    # Location of a tile that nicely represents the tileset.
    # Implementations may use this center value to set the default location
    # or to present a representative tile in a user interface
    centerPoint: Optional[TilePointType]
    # Tile matrix set definition
    tileMatrixSet: Optional[str]
    # Reference to a Tile Matrix Set on an official source
    tileMatrixSetURI: Optional[str]
    # Links to related resources.
    links: Optional[List[LinkType]]
