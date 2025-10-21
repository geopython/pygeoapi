# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2025 Francesco Bartoli
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
"""JSON-FG capabilities
Returns content as JSON-FG representations
"""

import json
import logging
import uuid
from typing import Union

from osgeo import gdal

from pygeoapi.formatter.base import BaseFormatter, FormatterSerializationError

LOGGER = logging.getLogger(__name__)


class JSONFGFormatter(BaseFormatter):
    """JSON-FG formatter"""

    def __init__(self, formatter_def: dict):
        """
        Initialize object

        :param formatter_def: formatter definition

        :returns: `pygeoapi.formatter.jsonfg.JSONFGFormatter`
        """

        geom = False
        if "geom" in formatter_def:
            geom = formatter_def["geom"]

        super().__init__({"name": "jsonfg", "geom": geom})
        self.mimetype = "application/vnd.ogc.fg+json"

    def write(self, data: dict, options: dict = {}) -> str:
        """
        Generate data in JSON-FG format

        :param options: JSON-FG formatting options
        :param data: dict of GeoJSON data

        :returns: string representation of format
        """

        try:
            if data.get("features"):
                fields = list(data["features"][0]["properties"].keys())
            else:
                fields = data["properties"].keys()
        except IndexError:
            LOGGER.error("no features")
            return str()

        LOGGER.debug(f"JSONFG fields: {fields}")

        try:
            output = geojson2jsonfg(data=data, dataset="items")
            return output
        except ValueError as err:
            LOGGER.error(err)
            raise FormatterSerializationError("Error writing JSONFG output")

    def __repr__(self):
        return f"<JSONFGFormatter> {self.name}"


def geojson2jsonfg(
    data: dict,
    dataset: str,
    identifier: Union[str, None] = None,
    id_field: str = "id",
) -> str:
    """
    Return JSON-FG from a GeoJSON content.

    :param cls: API object
    :param data: dict of data:

    :returns: string of rendered JSON (JSON-FG)
    """
    gdal.UseExceptions()
    LOGGER.debug("Dump GeoJSON content into a data source")
    # breakpoint()
    try:
        with gdal.OpenEx(json.dumps(data)) as srcDS:
            tmpfile = f"/vsimem/{uuid.uuid1()}.json"
            LOGGER.debug("Translate GeoJSON into a JSONFG memory file")
            gdal.VectorTranslate(tmpfile, srcDS, format="JSONFG")
            LOGGER.debug("Read JSONFG content from a memory file")
            data = gdal.VSIFOpenL(tmpfile, "rb")
            if not data:
                raise ValueError("Failed to read JSONFG content")
            gdal.VSIFSeekL(data, 0, 2)
            length = gdal.VSIFTellL(data)
            gdal.VSIFSeekL(data, 0, 0)
            jsonfg = json.loads(gdal.VSIFReadL(1, length, data).decode())
            return jsonfg
    except Exception as e:
        LOGGER.error(f"Failed to convert GeoJSON to JSON-FG: {e}")
        raise
    finally:
        gdal.VSIFCloseL(data)
