# =================================================================
#
# Authors: Antonio Cerciello <anto.nio.cerciello@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2022 Antonio Cerciello
# Copyright (c) 2026 Francesco Bartoli
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

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pygeoapi.models.provider.base import _validate_type


@dataclass
class VectorLayers:
    """TileJSON vector layer definition."""

    id: str = ''
    description: Optional[str] = None
    minzoom: Optional[int] = None
    maxzoom: Optional[int] = None
    fields: Optional[dict] = None

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
class MVTTilesJson:
    """TileJSON 3.0 specification."""

    tilejson: str = "3.0.0"
    name: Optional[str] = None
    tiles: Optional[str] = None
    minzoom: Optional[int] = None
    maxzoom: Optional[int] = None
    bounds: Optional[str] = None
    center: Optional[str] = None
    attribution: Optional[str] = None
    description: Optional[str] = None
    vector_layers: Optional[List[VectorLayers]] = None

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
            if (key == 'vector_layers'
                    and isinstance(value, list) and value):
                result[key] = [
                    item.model_dump(
                        exclude_none=exclude_none
                    ) if hasattr(item, 'model_dump')
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result
