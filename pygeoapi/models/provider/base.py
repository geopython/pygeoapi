# ****************************** -*-
# flake8: noqa
# =================================================================
#
# Authors: Antonio Cerciello <anto.nio.cerciello@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2022 Antonio Cerciello
# Copyright (c) 2023 Francesco Bartoli
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
    crs: Optional[str] = None


class LinkType(BaseModel):
    href: str
    rel: Optional[str] = None
    type_: Optional[str] = None
    hreflang: Optional[str] = None
    title: Optional[str] = None
    length: Optional[int] = None


class GeospatialDataType(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    dataType: DataTypeEnum = DataTypeEnum.VECTOR
    geometryDimension: Optional[GeometryDimensionEnum] = None
    maxTileMatrix: Optional[str] = None
    minTileMatrix: Optional[str] = None
    minScaleDenominator: Optional[float] = None
    maxScaleDenominator: Optional[float] = None
    minCellSize: Optional[float] = None
    maxCellSize: Optional[float] = None
    boundingBox: Optional[TwoDBoundingBoxType] = None
    links: Optional[LinkType] = None
    propertiesSchema: Optional[dict] = None


class StyleType(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    links: Optional[LinkType] = None


class TilePointType(BaseModel):
    crs: str
    coordinates: Optional[List[float]] = None
    scaleDenominator: Optional[float] = None
    cellSize: Optional[float] = None
    # CodeType as adaptation of MD_Identifier class ISO 19115
    tileMatrix: str
    cellSize: Optional[str] = None


class TileSetMetadata(BaseModel):
    # A title for this tileset
    title: Optional[str] = None
    # Brief narrative description of this tile set
    description: Optional[str] = None
    # keywords about this tileset
    keywords: Optional[List[str]] = None
    # Version of the Tile Set. Changes if the data behind the tiles
    # has been changed
    version: Optional[str] = None
    # Useful information to contact the authors or custodians for the Tile Set
    pointOfContact: Optional[str] = None
    # Short reference to recognize the author or provider
    attribution: Optional[str] = None
    # License applicable to the tiles
    license_: Optional[str] = None
    # Restrictions on the availability of the Tile Set that the user needs to
    # be aware of before using or redistributing the Tile Set
    accessConstraints: Optional[AccessConstraintsEnum] = AccessConstraintsEnum.UNCLASSIFIED
    # Media types available for the tiles
    mediaTypes:  Optional[List[str]] = None
    # Type of data represented in the tileset
    dataType: DataTypeEnum = DataTypeEnum.VECTOR
    # Limits for the TileRow and TileCol values for each TileMatrix in the
    # tileMatrixSet. If missing, there are no limits other that the ones
    # imposed by the TileMatrixSet. If present the TileMatrices listed are
    # limited and the rest not available at all
    tileMatrixSetLimits: Optional[TileMatrixLimitsType] = None
    # Coordinate Reference System (CRS)
    crs: Optional[str] = None
    # Epoch of the Coordinate Reference System (CRS)
    epoch: Optional[int] = None
    # Minimum bounding rectangle surrounding the tile matrix set, in the
    # supported CRS
    boundingBox: Optional[TwoDBoundingBoxType] = None
    # When the Tile Set was first produced
    created: Optional[datetime] = None
    # Last Tile Set change/revision
    updated: Optional[datetime] = None
    layers: Optional[GeospatialDataType] = None
    # Style involving all layers used to generate the tileset
    style: Optional[StyleType] = None
    # Location of a tile that nicely represents the tileset.
    # Implementations may use this center value to set the default location
    # or to present a representative tile in a user interface
    centerPoint: Optional[TilePointType] = None
    # Tile matrix set definition
    tileMatrixSet: Optional[str] = None
    # Reference to a Tile Matrix Set on an official source
    tileMatrixSetURI: Optional[str] = None
    # Links to related resources.
    links: Optional[List[LinkType]] = None
