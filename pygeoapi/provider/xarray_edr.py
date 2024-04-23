# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 Tom Kralidis
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

import numpy as np

from pygeoapi.provider.base import ProviderNoDataError, ProviderQueryError
from pygeoapi.provider.base_edr import BaseEDRProvider
from pygeoapi.provider.xarray_ import (
    _to_datetime_string,
    _convert_float32_to_float64,
    XarrayProvider,
)

LOGGER = logging.getLogger(__name__)


class XarrayEDRProvider(BaseEDRProvider, XarrayProvider):
    """EDR Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.rasterio_.RasterioProvider
        """

        BaseEDRProvider.__init__(self, provider_def)
        XarrayProvider.__init__(self, provider_def)

    @BaseEDRProvider.register()
    def position(self, **kwargs):
        """
        Extract data from collection collection

        :param query_type: query type
        :param wkt: `shapely.geometry` WKT geometry
        :param datetime_: temporal (datestamp or extent)
        :param select_properties: list of parameters
        :param z: vertical level(s)
        :param format_: data format of output

        :returns: coverage data as dict of CoverageJSON or native format
        """

        query_params = {}

        LOGGER.debug(f'Query parameters: {kwargs}')

        LOGGER.debug(f"Query type: {kwargs.get('query_type')}")

        wkt = kwargs.get('wkt')
        if wkt is not None:
            LOGGER.debug('Processing WKT')
            LOGGER.debug(f'Geometry type: {wkt.type}')
            if wkt.type == 'Point':
                query_params[self._coverage_properties['x_axis_label']] = wkt.x
                query_params[self._coverage_properties['y_axis_label']] = wkt.y
            elif wkt.type == 'LineString':
                query_params[self._coverage_properties['x_axis_label']] = wkt.xy[0]  # noqa
                query_params[self._coverage_properties['y_axis_label']] = wkt.xy[1]  # noqa
            elif wkt.type == 'Polygon':
                query_params[self._coverage_properties['x_axis_label']] = slice(wkt.bounds[0], wkt.bounds[2])  # noqa
                query_params[self._coverage_properties['y_axis_label']] = slice(wkt.bounds[1], wkt.bounds[3])  # noqa
                pass

        LOGGER.debug('Processing parameter-name')
        select_properties = kwargs.get('select_properties')

        # example of fetching instance passed
        # TODO: apply accordingly
        instance = kwargs.get('instance')
        LOGGER.debug(f'instance: {instance}')

        datetime_ = kwargs.get('datetime_')
        if datetime_ is not None:
            query_params[self.time_field] = self._make_datetime(datetime_)

        LOGGER.debug(f'query parameters: {query_params}')

        try:
            if select_properties:
                self.fields = {k: v for k, v in self.fields.items() if k in select_properties}  # noqa
                data = self._data[[*select_properties]]
            else:
                data = self._data

            if self.time_field in query_params:
                remaining_query = {
                    key: val for key, val in query_params.items()
                    if key != self.time_field
                }
                if isinstance(query_params[self.time_field], slice):
                    time_query = {
                        self.time_field: query_params[self.time_field]
                    }
                else:
                    time_query = {
                        self.time_field: (
                                data[self.time_field].dt.date ==
                                query_params[self.time_field]
                        )
                    }
                data = data.sel(
                    time_query).sel(remaining_query, method='nearest')
            else:
                data = data.sel(query_params, method='nearest')
        except KeyError:
            raise ProviderNoDataError()

        try:
            height = data.sizes[self.y_field]
        except KeyError:
            height = 1
        try:
            width = data.sizes[self.x_field]
        except KeyError:
            width = 1
        time, time_steps = self._parse_time_metadata(data, kwargs)

        bbox = wkt.bounds
        out_meta = {
            'bbox': [bbox[0], bbox[1], bbox[2], bbox[3]],
            "time": time,
            "driver": "xarray",
            "height": height,
            "width": width,
            "time_steps": time_steps,
            "variables": {var_name: var.attrs
                          for var_name, var in data.variables.items()}
        }

        return self.gen_covjson(out_meta, data, self.fields)

    @BaseEDRProvider.register()
    def cube(self, **kwargs):
        """
        Extract data from collection

        :param query_type: query type
        :param bbox: `list` of minx,miny,maxx,maxy coordinate values as `float`
        :param datetime_: temporal (datestamp or extent)
        :param select_properties: list of parameters
        :param z: vertical level(s)
        :param format_: data format of output

        :returns: coverage data as dict of CoverageJSON or native format
        """

        query_params = {}

        LOGGER.debug(f'Query parameters: {kwargs}')

        LOGGER.debug(f"Query type: {kwargs.get('query_type')}")

        bbox = kwargs.get('bbox')
        xmin, ymin, xmax, ymax = self._configure_bbox(bbox)

        if len(bbox) == 4:
            query_params[self.x_field] = slice(bbox[xmin], bbox[xmax])
            query_params[self.y_field] = slice(bbox[ymin], bbox[ymax])
        else:
            raise ProviderQueryError('z-axis not supported')

        LOGGER.debug('Processing parameter-name')
        select_properties = kwargs.get('select_properties')

        # example of fetching instance passed
        # TODO: apply accordingly
        instance = kwargs.get('instance')
        LOGGER.debug(f'instance: {instance}')

        datetime_ = kwargs.get('datetime_')
        if datetime_ is not None:
            query_params[self.time_field] = self._make_datetime(datetime_)

        LOGGER.debug(f'query parameters: {query_params}')
        try:
            if select_properties:
                self.fields = {k: v for k, v in self.fields.items() if k in select_properties}  # noqa
                data = self._data[[*select_properties]]
            else:
                data = self._data
            data = data.sel(query_params)
            data = _convert_float32_to_float64(data)
        except KeyError:
            raise ProviderNoDataError()

        height = data.sizes[self.y_field]
        width = data.sizes[self.x_field]
        time, time_steps = self._parse_time_metadata(data, kwargs)

        out_meta = {
            'bbox': [
                data.coords[self.x_field].values[0],
                data.coords[self.y_field].values[0],
                data.coords[self.x_field].values[-1],
                data.coords[self.y_field].values[-1]
            ],
            "time": time,
            "driver": "xarray",
            "height": height,
            "width": width,
            "time_steps": time_steps,
            "variables": {var_name: var.attrs
                          for var_name, var in data.variables.items()}
        }

        return self.gen_covjson(out_meta, data, self.fields)

    def _make_datetime(self, datetime_):
        """
        Make xarray datetime query

        :param datetime_: temporal (datestamp or extent)

        :returns: xarray datetime query
        """
        datetime_ = datetime_.rstrip('Z').replace('Z/', '/')
        if '/' in datetime_:
            begin, end = datetime_.split('/')
            if begin == '..':
                begin = self._data[self.time_field].min().values
            if end == '..':
                end = self._data[self.time_field].max().values
            if np.datetime64(begin) < np.datetime64(end):
                return slice(begin, end)
            else:
                LOGGER.debug('Reversing slicing from high to low')
                return slice(end, begin)
        else:
            return np.datetime64(datetime_)

    def _get_time_range(self, data):
        """
        Make xarray dataset temporal extent

        :param data: xarray dataset

        :returns: list of temporal extent
        """
        time = data.coords[self.time_field]
        if time.size == 0:
            raise ProviderNoDataError()
        else:
            start = _to_datetime_string(data[self.time_field].values.min())
            end = _to_datetime_string(data[self.time_field].values.max())
        return [start, end]

    def _parse_time_metadata(self, data, kwargs):
        """
        Parse time information for output metadata.

        :param data: xarray dataset
        :param kwargs: dictionary

        :returns: list of temporal extent, number of timesteps
        """
        try:
            time = self._get_time_range(data)
        except KeyError:
            time = []
        try:
            time_steps = data.coords[self.time_field].size
        except KeyError:
            time_steps = kwargs.get('limit')
        return time, time_steps

    def _configure_bbox(self, bbox):
        xmin, ymin, xmax, ymax = 0, 1, 2, 3
        if self._data[self.x_field][0] > self._data[self.x_field][-1]:
            xmin, xmax = xmax, xmin
        if self._data[self.y_field][0] > self._data[self.y_field][-1]:
            ymin, ymax = ymax, ymin
        return xmin, ymin, xmax, ymax
