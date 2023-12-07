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

from pydantic import BaseModel
from typing import List, Optional


class VectorLayers(BaseModel):
    id: str
    description: Optional[str]
    minzoom: Optional[int]
    maxzoom: Optional[int]
    fields: Optional[dict]


class MVTTilesJson(BaseModel):
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
