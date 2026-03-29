# =================================================================
#
# Authors: Antonio Cerciello <anto.nio.cerciello@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 Antonio Cerciello
# Copyright (c) 2026 Francesco Bartoli
# Copyright (c) 2025 Tom Kralidis
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

from dataclasses import dataclass, field, fields as dc_fields
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, get_type_hints

from pygeoapi.util import DEFINITIONSDIR

TMS_DIR = DEFINITIONSDIR / 'tiles'


def _validate_type(dc_instance: Any) -> None:
    """
    Validate field types on a dataclass instance.

    Checks each field value against its declared type,
    matching dataclass runtime type.
    Supports Optional[T], List[T], and plain types.

    :param dc_instance: dataclass instance to validate

    :raises ValueError: if a field value has the wrong type
    """
    hints = get_type_hints(dc_instance.__class__)
    for f in dc_fields(dc_instance):
        value = getattr(dc_instance, f.name)
        expected = hints[f.name]

        # Extract inner type from Optional[T]
        origin = getattr(expected, '__origin__', None)
        args = getattr(expected, '__args__', ())

        is_optional = (
            origin is type(None)  # noqa: E721
            or (origin is not None
                and type(None) in args)
        )

        if is_optional and value is None:
            continue

        # Unwrap Optional to get the inner type
        if is_optional and args:
            inner_types = [
                a for a in args if a is not type(None)
            ]
            if len(inner_types) == 1:
                expected = inner_types[0]
                origin = getattr(expected, '__origin__', None)
                args = getattr(expected, '__args__', ())

        # Check List[T]
        if origin is list:
            if not isinstance(value, list):
                raise ValueError(
                    f"{f.name} must be a list, "
                    f"got {type(value).__name__}"
                )
        # Check plain types (str, int, float, bool, Enum)
        elif origin is None:
            if isinstance(expected, type):
                # bool is subclass of int, check bool first
                if expected is bool:
                    if not isinstance(value, bool):
                        raise ValueError(
                            f"{f.name} must be a bool, "
                            f"got {type(value).__name__}"
                        )
                elif expected is int:
                    if isinstance(value, bool) \
                            or not isinstance(value, int):
                        raise ValueError(
                            f"{f.name} must be an int, "
                            f"got {type(value).__name__}"
                        )
                elif not isinstance(value, expected):
                    raise ValueError(
                        f"{f.name} must be a "
                        f"{expected.__name__}, "
                        f"got {type(value).__name__}"
                    )


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


@dataclass
class TileMatrixSetEnumType:
    """Tile matrix set definition loaded from JSON."""

    tileMatrixSet: str = ''
    tileMatrixSetURI: str = ''
    crs: str = ''
    title: str = ''
    orderedAxes: List[str] = field(default_factory=list)
    wellKnownScaleSet: str = ''
    tileMatrices: List[dict] = field(default_factory=list)

    def __post_init__(self):
        _validate_type(self)

    def model_dump(
        self, exclude_none: bool = False
    ) -> Dict[str, Any]:
        """Serialize to dict."""
        result = {
            'tileMatrixSet': self.tileMatrixSet,
            'tileMatrixSetURI': self.tileMatrixSetURI,
            'crs': self.crs,
            'title': self.title,
            'orderedAxes': self.orderedAxes,
            'wellKnownScaleSet': self.wellKnownScaleSet,
            'tileMatrices': self.tileMatrices,
        }
        if exclude_none:
            result = {
                k: v for k, v in result.items()
                if v is not None
            }
        return result


class TileMatrixSetLoader:
    def __init__(self, directory: Path):
        self.directory = directory

    def load_from_file(self, filename: str) -> TileMatrixSetEnumType:
        """
        Load a single TMS JSON file.

        :param filename: filename of TMS

        :returns: `TileMatrixSetEnumType` of TMS
        """

        filepath = self.directory / filename

        with filepath.open(encoding='utf-8') as fh:
            data = json.load(fh)

        return TileMatrixSetEnumType(
            tileMatrixSet=data["id"],
            tileMatrixSetURI=data["uri"],
            crs=data["crs"],
            title=data["title"],
            orderedAxes=data["orderedAxes"],
            wellKnownScaleSet=data.get("wellKnownScaleSet", ""),
            tileMatrices=data["tileMatrices"]
        )

    def create_enum(self) -> Enum:
        """
        Create an Enum with all TileMatrixSets in the directory.

        :returns: `Enum` of `TileMatrixSetEnum`
        """

        members = {}
        for filepath in self.directory.glob("*.json"):
            tms = self.load_from_file(filepath.name)
            enum_name = tms.tileMatrixSet.upper().replace("-", "").replace(" ", "")  # noqa
            members[enum_name] = tms

        return Enum("TileMatrixSetEnum", members)


tms_loader = TileMatrixSetLoader(TMS_DIR)
TileMatrixSetEnum = tms_loader.create_enum()


# Tile Set Metadata Sub Types

@dataclass
class TileMatrixLimitsType:
    """Tile matrix limits type."""

    tileMatrix: str = ''
    minTileRow: int = 0
    maxTileRow: int = 0
    minTileCol: int = 0
    maxTileCol: int = 0

    def __post_init__(self):
        _validate_type(self)

    def model_dump(
        self, exclude_none: bool = False
    ) -> Dict[str, Any]:
        """Serialize to dict."""
        result = {
            'tileMatrix': self.tileMatrix,
            'minTileRow': self.minTileRow,
            'maxTileRow': self.maxTileRow,
            'minTileCol': self.minTileCol,
            'maxTileCol': self.maxTileCol,
        }
        if exclude_none:
            result = {
                k: v for k, v in result.items()
                if v is not None
            }
        return result


@dataclass
class TwoDBoundingBoxType:
    """2D bounding box type."""

    lowerLeft: List[float] = field(default_factory=list)
    upperRight: List[float] = field(default_factory=list)
    crs: Optional[str] = None

    def __post_init__(self):
        _validate_type(self)

    def model_dump(
        self, exclude_none: bool = False
    ) -> Dict[str, Any]:
        """Serialize to dict."""
        result = {
            'lowerLeft': self.lowerLeft,
            'upperRight': self.upperRight,
            'crs': self.crs,
        }
        if exclude_none:
            result = {
                k: v for k, v in result.items()
                if v is not None
            }
        return result


@dataclass
class LinkType:
    """Link object."""

    href: str = ''
    rel: Optional[str] = None
    type_: Optional[str] = None
    hreflang: Optional[str] = None
    title: Optional[str] = None
    length: Optional[int] = None

    def __post_init__(self):
        _validate_type(self)

    def model_dump(
        self, exclude_none: bool = False
    ) -> Dict[str, Any]:
        """Serialize to dict.

        Note: Renames type_ to type for JSON output.
        """
        result = {
            'href': self.href,
            'rel': self.rel,
            'type': self.type_,
            'hreflang': self.hreflang,
            'title': self.title,
            'length': self.length,
        }
        if exclude_none:
            result = {
                k: v for k, v in result.items()
                if v is not None
            }
        return result


@dataclass
class GeospatialDataType:
    """Geospatial data reference type."""

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

    def __post_init__(self):
        _validate_type(self)

    def model_dump(
        self, exclude_none: bool = False
    ) -> Dict[str, Any]:
        """Serialize to dict."""
        result = {}
        for key, value in self.__dict__.items():
            if value is None and exclude_none:
                continue
            if hasattr(value, 'model_dump'):
                result[key] = value.model_dump(
                    exclude_none=exclude_none
                )
            elif isinstance(value, Enum):
                result[key] = value.value
            else:
                result[key] = value
        return result


@dataclass
class StyleType:
    """Style type definition."""

    id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    links: Optional[LinkType] = None

    def __post_init__(self):
        _validate_type(self)

    def model_dump(
        self, exclude_none: bool = False
    ) -> Dict[str, Any]:
        """Serialize to dict."""
        result = {}
        for key, value in self.__dict__.items():
            if value is None and exclude_none:
                continue
            if hasattr(value, 'model_dump'):
                result[key] = value.model_dump(
                    exclude_none=exclude_none
                )
            else:
                result[key] = value
        return result


@dataclass
class TilePointType:
    """Tile point type."""

    crs: str = ''
    coordinates: Optional[List[float]] = None
    scaleDenominator: Optional[float] = None
    cellSize: Optional[str] = None
    tileMatrix: str = ''

    def __post_init__(self):
        _validate_type(self)

    def model_dump(
        self, exclude_none: bool = False
    ) -> Dict[str, Any]:
        """Serialize to dict."""
        result = self.__dict__.copy()
        if exclude_none:
            result = {
                k: v for k, v in result.items()
                if v is not None
            }
        return result


@dataclass
class TileSetMetadata:
    """
    OGC Tile Set Metadata.

    Full metadata for a tileset compliant with
    OGC API - Tiles specification.
    """

    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    version: Optional[str] = None
    pointOfContact: Optional[str] = None
    attribution: Optional[str] = None
    license_: Optional[str] = None
    accessConstraints: Optional[AccessConstraintsEnum] = (
        AccessConstraintsEnum.UNCLASSIFIED
    )
    mediaTypes: Optional[List[str]] = None
    dataType: DataTypeEnum = DataTypeEnum.VECTOR
    tileMatrixSetLimits: Optional[TileMatrixLimitsType] = None
    crs: Optional[str] = None
    epoch: Optional[int] = None
    boundingBox: Optional[TwoDBoundingBoxType] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    layers: Optional[GeospatialDataType] = None
    style: Optional[StyleType] = None
    centerPoint: Optional[TilePointType] = None
    tileMatrixSet: Optional[str] = None
    tileMatrixSetURI: Optional[str] = None
    links: Optional[List[LinkType]] = None

    def __post_init__(self):
        _validate_type(self)

    def model_dump(
        self, exclude_none: bool = False
    ) -> Dict[str, Any]:
        """Serialize to dict.

        Handles nested models, enum values, and
        renames license_ to license for JSON output.
        """
        result = {}
        for key, value in self.__dict__.items():
            out_key = 'license' if key == 'license_' else key

            if value is None and exclude_none:
                continue

            if isinstance(value, list) and value:
                items = []
                for item in value:
                    if hasattr(item, 'model_dump'):
                        items.append(
                            item.model_dump(
                                exclude_none=exclude_none
                            )
                        )
                    else:
                        items.append(item)
                result[out_key] = items
            elif hasattr(value, 'model_dump'):
                result[out_key] = value.model_dump(
                    exclude_none=exclude_none
                )
            elif isinstance(value, Enum):
                result[out_key] = value.value
            elif isinstance(value, datetime):
                result[out_key] = value.isoformat()
            else:
                result[out_key] = value

        return result
