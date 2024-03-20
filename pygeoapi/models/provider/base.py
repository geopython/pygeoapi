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


class TilesMetadataFormat(str, Enum):
    # Tile Set Metadata
    JSON = "JSON"
    JSONLD = "JSONLD"
    # TileJSON 3.0
    TILEJSON = "TILEJSON"
    # HTML (default)
    HTML = "HTML"


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
    title: str
    orderedAxes: List[str]
    wellKnownScaleSet: str
    tileMatrices: List[dict]

class TileMatrixSetEnum(Enum):
    WORLDCRS84QUAD = TileMatrixSetEnumType(
        tileMatrixSet="WorldCRS84Quad",
        tileMatrixSetURI="http://www.opengis.net/def/tilematrixset/OGC/1.0/WorldCRS84Quad",  # noqa
        crs="http://www.opengis.net/def/crs/OGC/1.3/CRS84",
        title="World Mercator WGS84 (ellipsoid)",
        orderedAxes = ["Lon", "Lat"],
        wellKnownScaleSet = "http://www.opengis.net/def/wkss/OGC/1.0/GoogleCRS84Quad",
        tileMatrices = [
        {
            "id": "0",
            "scaleDenominator": 279541132.0143588781357,
            "cellSize": 0.703125,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 2,
            "matrixHeight": 1,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "1",
            "scaleDenominator": 139770566.0071794390678,
            "cellSize": 0.3515625,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 4,
            "matrixHeight": 2,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "2",
            "scaleDenominator": 69885283.0035897195339,
            "cellSize": 0.17578125,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 8,
            "matrixHeight": 4,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "3",
            "scaleDenominator": 34942641.501794859767,
            "cellSize": 0.087890625,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 16,
            "matrixHeight": 8,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "4",
            "scaleDenominator": 17471320.7508974298835,
            "cellSize": 0.0439453125,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 32,
            "matrixHeight": 16,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "5",
            "scaleDenominator": 8735660.3754487149417,
            "cellSize": 0.02197265625,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 64,
            "matrixHeight": 32,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "6",
            "scaleDenominator": 4367830.1877243574709,
            "cellSize": 0.010986328125,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 128,
            "matrixHeight": 64,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "7",
            "scaleDenominator": 2183915.0938621787354,
            "cellSize": 0.0054931640625,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 256,
            "matrixHeight": 128,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "8",
            "scaleDenominator": 1091957.5469310893677,
            "cellSize": 0.0027465820312,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 512,
            "matrixHeight": 256,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "9",
            "scaleDenominator": 545978.7734655446839,
            "cellSize": 0.0013732910156,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 1024,
            "matrixHeight": 512,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "10",
            "scaleDenominator": 272989.3867327723419,
            "cellSize": 0.0006866455078,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 2048,
            "matrixHeight": 1024,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "11",
            "scaleDenominator": 136494.693366386171,
            "cellSize": 0.0003433227539,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 4096,
            "matrixHeight": 2048,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "12",
            "scaleDenominator": 68247.3466831930855,
            "cellSize": 0.000171661377,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 8192,
            "matrixHeight": 4096,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "13",
            "scaleDenominator": 34123.6733415965427,
            "cellSize": 0.0000858306885,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 16384,
            "matrixHeight": 8192,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "14",
            "scaleDenominator": 17061.8366707982714,
            "cellSize": 0.0000429153442,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 32768,
            "matrixHeight": 16384,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "15",
            "scaleDenominator": 8530.9183353991357,
            "cellSize": 0.0000214576721,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 65536,
            "matrixHeight": 32768,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "16",
            "scaleDenominator": 4265.4591676995678,
            "cellSize": 0.0000107288361,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 131072,
            "matrixHeight": 65536,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "17",
            "scaleDenominator": 2132.7295838497839,
            "cellSize": 0.000005364418,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 262144,
            "matrixHeight": 131072,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "18",
            "scaleDenominator": 1066.364791924892,
            "cellSize": 0.000002682209,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 524288,
            "matrixHeight": 262144,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "19",
            "scaleDenominator": 533.182395962446,
            "cellSize": 0.0000013411045,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 1048576,
            "matrixHeight": 524288,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "20",
            "scaleDenominator": 266.591197981223,
            "cellSize": 0.0000006705523,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 2097152,
            "matrixHeight": 1048576,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "21",
            "scaleDenominator": 133.2955989906115,
            "cellSize": 0.0000003352761,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 4194304,
            "matrixHeight": 2097152,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "22",
            "scaleDenominator": 66.6477994953057,
            "cellSize": 0.0000001676381,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 8388608,
            "matrixHeight": 4194304,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "23",
            "scaleDenominator": 33.3238997476529,
            "cellSize": 0.000000083819,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 16777216,
            "matrixHeight": 8388608,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "24",
            "scaleDenominator": 16.6619498738264,
            "cellSize": 0.0000000419095,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 33554432,
            "matrixHeight": 16777216,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "25",
            "scaleDenominator": 8.3309749369132,
            "cellSize": 0.0000000209548,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 67108864,
            "matrixHeight": 33554432,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "26",
            "scaleDenominator": 4.1654874684566,
            "cellSize": 0.0000000104774,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 134217728,
            "matrixHeight": 67108864,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "27",
            "scaleDenominator": 2.0827437342283,
            "cellSize": 0.0000000052387,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 268435456,
            "matrixHeight": 134217728,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "28",
            "scaleDenominator": 1.0413718671142,
            "cellSize": 0.0000000026193,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 536870912,
            "matrixHeight": 268435456,
            "tileWidth": 256,
            "tileHeight": 256
        },
        {
            "id": "29",
            "scaleDenominator": 0.5206859335571,
            "cellSize": 0.0000000013097,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": [-180, 90],
            "matrixWidth": 1073741824,
            "matrixHeight": 536870912,
            "tileWidth": 256,
            "tileHeight": 256
        }
        ]
    )
    WEBMERCATORQUAD = TileMatrixSetEnumType(
        tileMatrixSet="WebMercatorQuad",
        tileMatrixSetURI="http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",  # noqa
        crs="http://www.opengis.net/def/crs/EPSG/0/3857",
        title="Google Maps Compatible for the World",
        orderedAxes=["E", "N"],
        wellKnownScaleSet="http://www.opengis.net/def/wkss/OGC/1.0/GoogleMapsCompatible",
        tileMatrices=[
      {
         "id" : "0",
         "scaleDenominator" : 559082264.0287177562714,
         "cellSize" : 156543.033928040968,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 1,
         "matrixHeight" : 1,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "1",
         "scaleDenominator" : 279541132.0143588781357,
         "cellSize" : 78271.516964020484,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 2,
         "matrixHeight" : 2,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "2",
         "scaleDenominator" : 139770566.0071794390678,
         "cellSize" : 39135.758482010242,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 4,
         "matrixHeight" : 4,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "3",
         "scaleDenominator" : 69885283.0035897195339,
         "cellSize" : 19567.879241005121,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 8,
         "matrixHeight" : 8,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "4",
         "scaleDenominator" : 34942641.501794859767,
         "cellSize" : 9783.9396205025605,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 16,
         "matrixHeight" : 16,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "5",
         "scaleDenominator" : 17471320.7508974298835,
         "cellSize" : 4891.9698102512803,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 32,
         "matrixHeight" : 32,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "6",
         "scaleDenominator" : 8735660.3754487149417,
         "cellSize" : 2445.9849051256401,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 64,
         "matrixHeight" : 64,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "7",
         "scaleDenominator" : 4367830.1877243574709,
         "cellSize" : 1222.9924525628201,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 128,
         "matrixHeight" : 128,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "8",
         "scaleDenominator" : 2183915.0938621787354,
         "cellSize" : 611.49622628141,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 256,
         "matrixHeight" : 256,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "9",
         "scaleDenominator" : 1091957.5469310893677,
         "cellSize" : 305.748113140705,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 512,
         "matrixHeight" : 512,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "10",
         "scaleDenominator" : 545978.7734655446839,
         "cellSize" : 152.8740565703525,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 1024,
         "matrixHeight" : 1024,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "11",
         "scaleDenominator" : 272989.3867327723419,
         "cellSize" : 76.4370282851763,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 2048,
         "matrixHeight" : 2048,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "12",
         "scaleDenominator" : 136494.693366386171,
         "cellSize" : 38.2185141425881,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 4096,
         "matrixHeight" : 4096,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "13",
         "scaleDenominator" : 68247.3466831930855,
         "cellSize" : 19.1092570712941,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 8192,
         "matrixHeight" : 8192,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "14",
         "scaleDenominator" : 34123.6733415965427,
         "cellSize" : 9.554628535647,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 16384,
         "matrixHeight" : 16384,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "15",
         "scaleDenominator" : 17061.8366707982714,
         "cellSize" : 4.7773142678235,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 32768,
         "matrixHeight" : 32768,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "16",
         "scaleDenominator" : 8530.9183353991357,
         "cellSize" : 2.3886571339118,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 65536,
         "matrixHeight" : 65536,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "17",
         "scaleDenominator" : 4265.4591676995678,
         "cellSize" : 1.1943285669559,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 131072,
         "matrixHeight" : 131072,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "18",
         "scaleDenominator" : 2132.7295838497839,
         "cellSize" : 0.5971642834779,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 262144,
         "matrixHeight" : 262144,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "19",
         "scaleDenominator" : 1066.364791924892,
         "cellSize" : 0.298582141739,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 524288,
         "matrixHeight" : 524288,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "20",
         "scaleDenominator" : 533.182395962446,
         "cellSize" : 0.1492910708695,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 1048576,
         "matrixHeight" : 1048576,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "21",
         "scaleDenominator" : 266.591197981223,
         "cellSize" : 0.0746455354347,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 2097152,
         "matrixHeight" : 2097152,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "22",
         "scaleDenominator" : 133.2955989906115,
         "cellSize" : 0.0373227677174,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 4194304,
         "matrixHeight" : 4194304,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "23",
         "scaleDenominator" : 66.6477994953057,
         "cellSize" : 0.0186613838587,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 8388608,
         "matrixHeight" : 8388608,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "24",
         "scaleDenominator" : 33.3238997476529,
         "cellSize" : 0.0093306919293,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 16777216,
         "matrixHeight" : 16777216,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "25",
         "scaleDenominator" : 16.6619498738264,
         "cellSize" : 0.0046653459647,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 33554432,
         "matrixHeight" : 33554432,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "26",
         "scaleDenominator" : 8.3309749369132,
         "cellSize" : 0.0023326729823,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 67108864,
         "matrixHeight" : 67108864,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "27",
         "scaleDenominator" : 4.1654874684566,
         "cellSize" : 0.0011663364912,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 134217728,
         "matrixHeight" : 134217728,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "28",
         "scaleDenominator" : 2.0827437342283,
         "cellSize" : 0.0005831682456,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 268435456,
         "matrixHeight" : 268435456,
         "tileWidth" : 256,
         "tileHeight" : 256
      },
      {
         "id" : "29",
         "scaleDenominator" : 1.0413718671142,
         "cellSize" : 0.0002915841228,
         "cornerOfOrigin" : "topLeft",
         "pointOfOrigin" : [ -20037508.3427892439067, 20037508.3427892439067 ],
         "matrixWidth" : 536870912,
         "matrixHeight" : 536870912,
         "tileWidth" : 256,
         "tileHeight" : 256
      }
    ]
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
