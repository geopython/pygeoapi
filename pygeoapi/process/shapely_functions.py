# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Emmanuel Jolaiya <jolaiyaemmanuel@gmail.com>
#
# Copyright (c) 2024 Tom Kralidis
# Copyright (c) 2024 Emmanuel Jolaiya
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

import enum
import logging

from typing import Any, Dict, List, Tuple, Union

from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.prepared import prep
from shapely.wkt import loads

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError


LOGGER = logging.getLogger(__name__)


class SupportedShapelyOperations(enum.Enum):
    """
    Enum for the supported shapely operations
    """

    # Measurement operations.
    # Ref: https://shapely.readthedocs.io/en/stable/measurement.html

    MEASUREMENT_AREA = "measurement:area"
    MEASUREMENT_DISTANCE = "measurement:distance"
    MEASUREMENT_BOUNDS = "measurement:bounds"

    # Predicate operations.
    # Ref: https://shapely.readthedocs.io/en/stable/predicates.html

    PREDICATES_COVERS = "predicates:covers"
    PREDICATES_WITHIN = "predicates:within"

    # Set operations.
    # Ref: https://shapely.readthedocs.io/en/stable/set_operations.html

    SET_DIFFERENCE = "set:difference"
    SET_UNION = "set:union"

    # Constructive operations.
    # Ref: https://shapely.readthedocs.io/en/stable/constructive.html

    CONSTRUCTIVE_BUFFER = "constructive:buffer"
    CONSTRUCTIVE_CENTROID = "constructive:centroid"


class SupportedFormats(enum.Enum):
    WKT = "wkt"
    """Well Known Text"""
    GeoJSON_GEOMETRY = "geojson"
    """GeoJSON Geometry"""


class SupportedGeometryTypes(enum.Enum):
    POINT = "Point"
    POLYGON = "Polygon"
    MULTI_POLYGON = "MultiPolygon"


#: Process metadata and description
PROCESS_METADATA = {
    "version": "0.2.0",
    "id": "shapely-functions",
    "title": {
        "en": "Shapely Functions",
        "fr": "Fonctions galbées",
        "es": "Funciones bien formadas"
    },
    "description": {
        "en": "An example process that takes one or more input geometry "
        "(WKT or GeoJSON geometry), applies the specified shapely"
        " operation on the input, and returns the result "
        "in the specified output_format.",
        "fr": "Un exemple de processus qui prend une ou plusieurs géométries"
        " d'entrée (géométrie WKT ou GeoJSON) applique l'opération "
        "galbée spécifiée sur l'entrée et renvoie le "
        "résultat dans le format de sortie spécifié.",
        "es": "Un proceso de ejemplo que toma una o más geometrías"
        "de entrada (geometría WKT o GeoJSON) aplica la operación"
        "de forma especificada en la entrada y devuelve el resultado"
        "en el formato de salida especificado."
    },
    "jobControlOptions": ["sync-execute", "async-execute"],
    "keywords": [
        "shapely functions",
        "measurement",
        "predicates",
        "set operations",
        "constructive ops"
    ],
    "links": [
        {
            "type": "text/html",
            "rel": "about",
            "title": "information",
            "href": "https://shapely.readthedocs.io",
            "hreflang": "en-US"
        },
    ],
    "inputs": {
        "operation": {
            "title": "Shapely operation",
            "description": "The shapely operation to perform. Namespace of the"
            "function category is used to avoid mixup in function names.",
            "schema": {
                "type": "string"
            },
            "minOccurs": 1,
            "maxOccurs": 1,
            "enum": [ops.value for ops in SupportedShapelyOperations]
        },
        "geoms": {
            "title": "Input geometry",
            "description": "The representation of the object"
            " as GeoJSON geometry or a WKT.",
            "schema": {
                "type": "array",
                "description": "An array of the geometries. "
                "The order of the geometries matter. The first "
                "element is considered geom A, second element as geom B, "
                "in that order.",
                "minItems": 1,
                "maxItems": 2,
                "items": {
                    "oneOf": [
                        # Can be a WKT string
                        {
                            "type": "string",
                        },
                        # or a GeoJSON geometry
                        {
                            "oneOf": [
                                {"format": "geojson-geometry"},
                                {
                                    "$ref": "http://schemas.opengis.net/"
                                    "ogcapi/features/part1/1.0/openapi/"
                                    "schemas/geometryGeoJSON.yaml"
                                },
                            ]
                        },
                    ]
                },
            },
            "minOccurs": 1,
            "maxOccurs": 1,
        },
        "output_format": {
            "title": "The output format of the geometry",
            "description": "The output format of the process result. "
            "If the shapely operation does not return a geometry, then "
            " this is ignored.",
            "schema": {
                "type": "string"
            },
            "minOccurs": 0,
            "maxOccurs": 1,
            "enum": [v.value for v in SupportedFormats]
        },
    },
    "outputs": {
        "result": {
            "title": "Shapely operation result",
            "description": "The result of the shapely operation "
            "performed in the process.",
            "schema": {
                "type": "object",
                "contentMediaType": "application/json"
            },
        },
    },
    "example": {
        "inputs": {
            "operation": "predicates:within",
            "geoms": [
                {
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
                {
                    "coordinates": [
                        [
                            [80.58983993887352, 24.07996699713047],
                            [80.58983993887352, 20.291958215654446],
                            [85.04987314197012, 20.291958215654446],
                            [85.04987314197012, 24.07996699713047],
                            [80.58983993887352, 24.07996699713047],
                        ]
                    ],
                    "type": "Polygon"
                },
            ],
        }
    },
}


class ShapelyFunctionsProcessor(BaseProcessor):
    """Shapely Functions Processor example"""

    def __init__(self, processor_def):
        """
        Initialize object

        :param processor_def: provider definition

        :returns: pygeoapi.process.shapely_functions.ShapelyFunctionsProcessor
        """
        self.shapely_operations = [ops.value for ops in SupportedShapelyOperations]  # noqa: E501
        self.supported_formats = [fmt.value for fmt in SupportedFormats]
        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data) -> Tuple[str, Dict[str, Any]]:
        mimetype = "application/json"
        operation = data.get("operation")
        output_format = data.get("output_format")
        geometries = data.get("geoms")

        # validations
        if geometries is None:
            raise ProcessorExecuteError("Cannot process without valid geometries.")  # noqa: E501

        if not isinstance(geometries, list):
            raise ProcessorExecuteError(
                """Cannot process without valid geometries.
                `geoms` must be an array of WKT
                 or GeoJSON geometry objects."""
            )

        # output_format could be optional,
        # because some operations return only value and not geometry
        nongeom_operations = {
            SupportedShapelyOperations.MEASUREMENT_AREA.value,
            SupportedShapelyOperations.MEASUREMENT_DISTANCE.value,
            SupportedShapelyOperations.MEASUREMENT_BOUNDS.value,
            SupportedShapelyOperations.PREDICATES_COVERS.value,
            SupportedShapelyOperations.PREDICATES_WITHIN.value
        }
        if output_format is None and operation not in nongeom_operations:
            raise ProcessorExecuteError("Cannot process without an `output_format`.")  # noqa: E501

        if (
            output_format is not None
            and output_format.lower() not in self.supported_formats
        ):
            raise ProcessorExecuteError(
                f"""Invalid `output_format` provided.
                Supported options are {self.supported_formats},
                but got {output_format}."""
            )

        self.output_format = output_format

        if operation is None:
            raise ProcessorExecuteError("Cannot process without a valid operation.")  # noqa: E501

        if operation not in self.shapely_operations:
            raise ProcessorExecuteError(
                f"""Invalid shapely operation provided.
                Supported operations are : {self.shapely_operations}"""
            )

        requires_single_geom = {
            SupportedShapelyOperations.MEASUREMENT_AREA.value,
            SupportedShapelyOperations.MEASUREMENT_BOUNDS.value,
            SupportedShapelyOperations.CONSTRUCTIVE_BUFFER.value,
            SupportedShapelyOperations.CONSTRUCTIVE_CENTROID.value
        }

        if operation in requires_single_geom and len(geometries) > 1:
            raise ProcessorExecuteError(
                f"""Too many geometries. The {operation}
                    operation requires only one geometry,
                    but {len(geometries)} was provided."""
            )

        if operation not in requires_single_geom and len(geometries) < 2:
            raise ProcessorExecuteError(
                f"""Too few geometries. The {operation} operation
                    requires at least two geometry,
                    but {len(geometries)} was provided."""
            )

        parsed_geoms = []

        for geom in geometries:
            if isinstance(geom, str):
                parsed_geoms.append(loads(geom))
            else:
                parsed_geoms.append(shape(geom))

        result = self.perform_operation(parsed_geoms, operation)

        return mimetype, result

    def parse_result(self, geom: BaseGeometry) -> Union[str, Dict[str, Any]]:
        """
        Convert a shapely geometry into the specified format by the client.

        Args:
            geom (BaseGeometry): The shapely geometry to convert.

        Returns:
            Union[str,Dict[str,Any]]: The resulting geometry
            in the specified format.
        """
        return (
            geom.wkt
            if self.output_format == SupportedFormats.WKT.value
            else mapping(geom)
        )

    def perform_operation(self, parsed_geoms: List[BaseGeometry], operation: str):  # noqa: E501
        """
        Perform the exact shapely operation specified by the client.

        Args:
            parsed_geoms (List[BaseGeometry]): An array of shapely geometries.
            operation (str): The exact shapely operation to perform.

        Raises:
            ProcessorExecuteError: Server error if given an invalid parameter.

        Returns:
            Dict[str,Any]: The response object with the operation result,
            to be returned to the client.
        """
        result = {"operation": operation, "result": None}

        #  prep the first geom for performance improvement
        prep(parsed_geoms[0])
        if operation == SupportedShapelyOperations.MEASUREMENT_AREA.value:
            if parsed_geoms[0].type not in [
                SupportedGeometryTypes.POLYGON.value,
                SupportedGeometryTypes.MULTI_POLYGON.value
            ]:
                raise ProcessorExecuteError(
                    f"""Invalid geometry type.{operation}
                        operation only works on
                        `Polygon and MultiPolygon` geometry."""
                )
            result.update({"result": parsed_geoms[0].area})
        elif operation == SupportedShapelyOperations.MEASUREMENT_BOUNDS.value:
            result.update({"result": parsed_geoms[0].bounds})
        elif operation == SupportedShapelyOperations.MEASUREMENT_DISTANCE.value:  # noqa: E501
            result.update({"result": parsed_geoms[0].distance(parsed_geoms[1])})  # noqa: E501
        elif operation == SupportedShapelyOperations.PREDICATES_COVERS.value:
            result.update({"result": parsed_geoms[0].covers(parsed_geoms[1])})
        elif operation == SupportedShapelyOperations.PREDICATES_WITHIN.value:
            result.update({"result": parsed_geoms[0].within(parsed_geoms[1])})
        elif operation == SupportedShapelyOperations.SET_DIFFERENCE.value:
            result.update(
                {
                    "result": self.parse_result(
                        parsed_geoms[0].difference(parsed_geoms[1])
                    )
                }
            )
        elif operation == SupportedShapelyOperations.SET_UNION.value:
            result.update(
                {
                    "result": self.parse_result(parsed_geoms[0].union(parsed_geoms[1]))  # noqa: E501
                }
            )
        elif operation == SupportedShapelyOperations.CONSTRUCTIVE_BUFFER.value:
            # todo - how do we receive kwargs from the user?
            result.update({"result": self.parse_result(parsed_geoms[0].buffer(10))})  # noqa: E501
        else:
            result.update({"result": self.parse_result(parsed_geoms[0].centroid)})  # noqa: E501
        return result

    def __repr__(self):
        return f"<ShapelyFunctionsProcessor> {self.name}"
