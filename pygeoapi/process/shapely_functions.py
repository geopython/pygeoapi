# =================================================================
#
# Authors: Krishna Lodha <krishna@rottengrapes.com>
#
# Copyright (c) 2023 Krishna Lodha
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

import logging

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError
from shapely.geometry import shape
from shapely import wkt
import json

LOGGER = logging.getLogger(__name__)

#: Process metadata and description
PROCESS_METADATA = {
    "version": "0.0.1",
    "id": "shapely-geometry-contains",
    "title": {"en": "Shapely Contains function", "fr": "Shapely Contains function"},
    "description": {
        "en": "An example process that takes 2 geometries (A & B) in WKT"
        "or GeoJSON format and returns Boolean representing"
        "if B is completely withing A",
        "fr": """Un exemple de processus qui prend 2 géométries (A et B) """
        """au format WKT ou GeojSON et retourne une valeur booléenne """
        """représentant si B est complètement à l'intérieur de A""",
    },
    "jobControlOptions": ["sync-execute", "async-execute"],
    "keywords": [
        "contains",
        "shapely",
    ],
    "links": [
        {
            "type": "text/html",
            "rel": "about",
            "title": "information",
            "href": "https://shapely.readthedocs.io/en/stable/manual.html#object.contains",
            "hreflang": "en-US",
        }
    ],
    "inputs": {
        "A": {
            "title": "Geometry A",
            "description": "Bigger geometry in which geometry B should be",
            "schema": {"type": "dict"},
            "minOccurs": 1,
            "maxOccurs": 1,
            "metadata": None,  # TODO how to use?
            "keywords": [
                "Geometry A",
            ],
        },
        "B": {
            "title": "Geometry B",
            "description": "Geometry to be tested against geometry A",
            "schema": {"type": "dict"},
            "minOccurs": 1,
            "maxOccurs": 1,
            "metadata": None,  # TODO how to use?
            "keywords": [
                "Geometry B",
            ],
        },
    },
    "outputs": {
        "result": {
            "Contains": True,
        }
    },
    "example": {
        {
            "inputs": {
                "A": {
                    "geometry": {
                        "coordinates": [
                            [
                                [80.58983993887352, 24.07996699713047],
                                [80.58983993887352, 20.291958215654446],
                                [85.04987314197012, 20.291958215654446],
                                [85.04987314197012, 24.07996699713047],
                                [80.58983993887352, 24.07996699713047],
                            ]
                        ],
                        "type": "Polygon",
                    },
                    "type": "geojson",
                },
                "B": {
                    "geometry": "POINT(83.27651071580385 22.593553859283745)",
                    "type": "wkt",
                },
            }
        }
    },
}


class ShapelyContainsProcessor(BaseProcessor):
    """Shapely Contain Processor example"""

    def __init__(self, processor_def):
        """
        Initialize object

        :param processor_def: provider definition

        :returns: pygeoapi.process.shapely_functions.ShapelyContainsProcessor
        """

        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data):
        mimetype = "application/json"
        geomA = data.get("A")
        geomB = data.get("B")
        if geomA is None or geomB is None:
            raise ProcessorExecuteError("Cannot process without geometries")

        geometryA = _get_geometry(geomA)
        geometryB = _get_geometry(geomB)

        if geometryA.contains(geometryB):
            contain = True
        else:
            contain = False

        outputs = {"id": "result", "Contains": contain}
        return mimetype, outputs

    def __repr__(self):
        return f"<ShapelyContainsProcessor> {self.name}"


# Check if geometry is valid and either WKT or GeoJSON feature
def _get_geometry(input):
    try:
        if input["type"].lower() == "wkt":
            geometry = wkt.loads(input["geometry"])
        elif input["type"].lower() == "geojson":
            geometry = shape(input["geometry"])
    except json.JSONDecodeError:
        raise ProcessorExecuteError(
            "Error: Input should be a dictionary with type and geometry keys"
        )
    # Check if the parsed geometry is valid
    return geometry
