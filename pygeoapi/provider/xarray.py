# =================================================================
#
# Authors: Gregory Petrochenkov <gpetrochenkov@usgs.gov>
#
# Copyright (c) 2020 Gregory Petrochenkov
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

import xarray
import numpy as np
import logging
import os
import uuid

from pygeoapi.provider.base import BaseProvider, ProviderConnectionError, ProviderQueryError

LOGGER = logging.getLogger(__name__)


class XarrayProvider(BaseProvider):
    """Provider class backed by local GeoJSON files
    This is meant to be simple
    (no external services, no dependencies, no schema)
    at the expense of performance
    (no indexing, full serialization roundtrip on each request)
    Not thread safe, a single server process is assumed
    This implementation uses the feature 'id' heavily
    and will override any 'id' provided in the original data.
    The feature 'properties' will be preserved.
    TODO:
    * query method should take bbox
    * instead of methods returning FeatureCollections,
    we should be yielding Features and aggregating in the view
    * there are strict id semantics; all features in the input GeoJSON file
    must be present and be unique strings. Otherwise it will break.
    * How to raise errors in the provider implementation such that
    * appropriate HTTP responses will be raised
    """

    def __init__(self, provider_def):
        """initializer"""
        BaseProvider.__init__(self, provider_def)

        try:
            zarr = self.data.split('.')[-1] == 'zarr'
            open_func = xarray.open_zarr if zarr else xarray.open_dataset
            self._data = open_func(self.data)
            self._coverage_properties = self._get_coverage_properties()

            self.axes = [self._coverage_properties['x_axis_label'],
                         self._coverage_properties['y_axis_label'],
                         self._coverage_properties['time_axis_label']]

            self.fields = self._coverage_properties['fields']
        except Exception as err:
            LOGGER.warning(err)
            raise ProviderConnectionError(err)

    def get_coverage_domainset(self):
        """
        Provide coverage domainset

        :returns: CIS JSON object of domainset metadata
        """

        domainset = {
            'type': 'DomainSetType',
            'generalGrid': {
                'type': 'GeneralGridCoverageType',
                'srsName': self._coverage_properties['bbox_crs'],
                'axisLabels': [
                    self._coverage_properties['x_axis_label'],
                    self._coverage_properties['y_axis_label']
                ],
                'axis': [{
                    'type': 'RegularAxisType',
                    'axisLabel': self._coverage_properties['x_axis_label'],
                    'lowerBound': self._coverage_properties['bbox'][0],
                    'upperBound': self._coverage_properties['bbox'][2],
                    'uomLabel': self._coverage_properties['bbox_units'],
                    'resolution': self._coverage_properties['resx']
                }, {
                    'type': 'RegularAxisType',
                    'axisLabel': self._coverage_properties['y_axis_label'],
                    'lowerBound': self._coverage_properties['bbox'][1],
                    'upperBound': self._coverage_properties['bbox'][3],
                    'uomLabel': self._coverage_properties['bbox_units'],
                    'resolution': self._coverage_properties['resy']
                },
                    {
                        'type': 'RegularAxisType',
                        'axisLabel': self._coverage_properties['time_axis_label'],
                        'lowerBound': self._coverage_properties['time_range'][0],
                        'upperBound': self._coverage_properties['time_range'][1],
                        'uomLabel': self._coverage_properties['restime'],
                        'resolution': self._coverage_properties['restime']
                    }
                ],
                'gridLimits': {
                    'type': 'GridLimitsType',
                    'srsName': 'http://www.opengis.net/def/crs/OGC/0/Index2D',
                    'axisLabels': ['i', 'j'],
                    'axis': [{
                        'type': 'IndexAxisType',
                        'axisLabel': 'i',
                        'lowerBound': 0,
                        'upperBound': self._coverage_properties['width']
                    }, {
                        'type': 'IndexAxisType',
                        'axisLabel': 'j',
                        'lowerBound': 0,
                        'upperBound': self._coverage_properties['height']
                    }]
                }
            },
            '_meta': {
                'tags': self._data.attrs
            }
        }

        return domainset

    def get_coverage_rangetype(self):
        """
        Provide coverage rangetype

        :returns: CIS JSON object of rangetype metadata
        """

        rangetype = {
            'type': 'DataRecordType',
            'field': []
        }

        for name, var in self._data.variables.items():
            LOGGER.debug('Determing rangetype for {}'.format(name))

            name, units = None, None
            if len(var.shape) >= 3:
                parameter = self._get_parameter_metadata(
                    name, var.attrs)
                name = parameter['description']
                units = parameter['unit_label']

                rangetype['field'].append({
                    'id': name,
                    'type': 'QuantityType',
                    'name': var.attrs.get('long_name') or name,
                    'definition': str(var.dtype),
                    'nodata': 'null',
                    'uom': {
                        'id': 'http://www.opengis.net/def/uom/UCUM/{}'.format(
                             units),
                        'type': 'UnitReference',
                        'code': units
                    },
                    '_meta': {
                        'tags': var.attrs
                    }
                })

        return rangetype

    def query(self, range_type=[], subsets={}, format_='json'):
        """
         Extract data from collection collection

        :param range_type: list of data variables to return (all if blank)
        :param subsets: dict of subset names with lists of ranges
        :param format_: data format of output

        :returns: coverage data as dict of CoverageJSON or native format
        """

        if len(range_type) < 1:
            range_type = self.fields

        data = self._data[[*range_type]]

        if(self._coverage_properties['x_axis_label'] in subsets or
           self._coverage_properties['y_axis_label'] in subsets or
           self._coverage_properties['time_axis_label'] in subsets):

            LOGGER.debug('Creating spatio-temporal subset')

            lon = self._coverage_properties['x_axis_label']
            lat = self._coverage_properties['y_axis_label']
            time = self._coverage_properties['time_axis_label']

            query_params = {}
            for key, val in subsets.items():
                query_params[key] = slice(val[0], val[1])

            data = data.sel(query_params)

        out_meta = {'bbox': [
            data.coords[self.lon_var].values[0],
            data.coords[self.lat_var].values[0],
            data.coords[self.lon_var].values[-1],
            data.coords[self.lat_var].values[-1]],
            "time": self._coverage_properties['time_range'],
            "driver": "Xarray",
            "height": data.dims[self.lat_var],
            "width": data.dims[self.lon_var],
            "time_steps": data.dims[self.time_var],
            "variables": {var_name: var.attrs
                          for var_name, var in data.variables.items()}
        }

        return self.gen_covjson(out_meta, data, range_type)

    def gen_covjson(self, metadata, data, range_type):
        """
        Generate coverage as CoverageJSON representation

        :param metadata: coverage metadata
        :param data: rasterio DatasetReader object
        :param range_type: range type list

        :returns: dict of CoverageJSON representation
        """

        LOGGER.debug('Creating CoverageJSON domain')
        minx, miny, maxx, maxy = metadata['bbox']
        mint, maxt = metadata['time']

        cj = {
            'type': 'Coverage',
            'domain': {
                'type': 'Domain',
                'domainType': 'Grid',
                'axes': {
                    self.lon_var: {
                        'start': minx,
                        'stop': maxx,
                        'num': metadata['width']
                    },
                    self.lat_var: {
                        'start': maxy,
                        'stop': miny,
                        'num': metadata['height']
                    },
                    self.time_var: {
                        'start': mint,
                        'stop': maxt,
                        'num': metadata['time_steps']
                    }
                },
                'referencing': [{
                    'coordinates': ['x', 'y'],
                    'system': {
                        'type': self._coverage_properties['crs_type'],
                        'id': self._coverage_properties['bbox_crs']
                    }
                }]
            },
            'parameters': {},
            'ranges': {}
        }

        for variable in range_type:
            pm = self._get_parameter_metadata(
                variable, self._data[variable].attrs)

            parameter = {
                'type': 'Parameter',
                'description': pm['description'],
                'unit': {
                    'symbol': pm['unit_label']
                },
                'observedProperty': {
                    'id': pm['observed_property_id'],
                    'label': {
                        'en': pm['observed_property_name']
                    }
                }
            }

            cj['parameters'][pm['id']] = parameter

        try:
            for key in cj['parameters'].keys():
                cj['ranges'][key] = {
                    'type': 'NdArray',
                    'dataType': str(self._data[variable].dtype),
                    'axisNames': [self._coverage_properties['x_axis_label'],
                                  self._coverage_properties['y_axis_label'],
                                  self._coverage_properties['time_axis_label']
                                  ],
                    'shape': [metadata['height'],
                              metadata['width'],
                              metadata['time_steps']]
                }

                cj['ranges'][key]['values'] = data[key].values.tolist()
        except IndexError as err:
            LOGGER.warning(err)
            raise ProviderQueryError('Invalid query parameter')

        return cj

    def _get_coverage_properties(self):
        """
        Helper function to normalize coverage properties

        :returns: `dict` of coverage properties
        """

        time_var, lat_var, lon_var = [None, None, None]
        for coord in self._data.coords:
            if coord.lower() == 'time':
                self.time_var = time_var = coord
                continue
            if self._data.coords[coord].attrs['units'] == 'degrees_north':
                self.lat_var = lat_var = coord
                continue
            if self._data.coords[coord].attrs['units'] == 'degrees_east':
                self.lon_var = lon_var = coord
                continue

        # It would be preferable to use CF attributes to get width
        # resolution etc but for now a generic approach is used to asess
        # all of the attributes based on lat lon vars
        properties = {
            'bbox': [
                self._data.coords[lon_var].values[0],
                self._data.coords[lat_var].values[0],
                self._data.coords[lon_var].values[-1],
                self._data.coords[lat_var].values[-1],
            ],
            'time_range': [
                np.datetime_as_string(self._data.coords[time_var].values[0]),
                np.datetime_as_string(self._data.coords[time_var].values[-1])
            ],
            'bbox_crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
            'crs_type': 'GeographicCRS',
            'x_axis_label': lon_var,
            'y_axis_label': lat_var,
            'time_axis_label': time_var,
            'width': self._data.dims[lon_var],
            'height': self._data.dims[lat_var],
            'time': self._data.dims[time_var],
            'time_duration': self.get_time_coverage_duration(),
            'bbox_units': 'degrees',
            'resx': np.abs(self._data.coords[lon_var].values[1]
                           - self._data.coords[lon_var].values[0]),
            'resy': np.abs(self._data.coords[lat_var].values[1]
                           - self._data.coords[lat_var].values[0]),
            'restime': self.get_time_resolution()
        }

        if 'crs' in self._data.variables.keys():
            properties['bbox_crs'] = '{}/{}'.format(
                'http://www.opengis.net/def/crs/OGC/1.3/',
                self._data.crs.epsg_code)

            properties['inverse_flattening'] = self_data.crs.inverse_flattening

            properties['crs_type'] = 'ProjectedCRS'

        properties['axes'] = [
            properties['x_axis_label'],
            properties['y_axis_label'],
            properties['time_axis_label']
        ]

        properties['fields'] =  [name for name in self._data.variables
                          if len(self._data.variables[name].shape) >= 3]

        return properties

    @staticmethod
    def _get_parameter_metadata(name, attrs):
        """
        Helper function to derive parameter name and units
        :param name: name of variable
        :param attrs: dictionary of variable attributes
        :returns: dict of parameter metadata
        """

        return {
            'id': name,
            'description': attrs.get('long_name') or 'Not available',
            'unit_label': attrs.get('units') or 'Not available',
            'unit_symbol': attrs.get('units') or 'Not available',
            'observed_property_id': name,
            'observed_property_name': attrs.get('long_name') or 'Not available'
        }

    def get_time_resolution(self):
        """
        Helper function to derive time resolution
        :returns: time resolution string
        """
        dts = np.array([(self._data.TIME[1] - self._data.TIME[0])
                       .values.astype('timedelta64[%s]' % x) for x in
                      ['Y', 'M', 'D', 'h', 'm', 's', 'ms']])
        return str(dts[np.array([x.astype(np.int) for x in dts]) > 0][0])

    def get_time_coverage_duration(self):
        """
        Helper function to derive time coverage duration
        :returns: time coverage duration string
        """
        ms_difference = (self._data.TIME[-1] - self._data.TIME[0])\
            .values.astype('timedelta64[ms]').astype(np.double)
        time_dict = {
            'days': int(ms_difference / 1000 / 60 / 60 / 24),
            'hours': int((ms_difference / 1000 / 60 / 60) % 24),
            'minutes': int((ms_difference / 1000 / 60) % 60),
            'seconds': int(ms_difference / 1000) % 60}
        times = ['%d %s' % (val, key) for key, val in time_dict.items() if val > 0]
        return ', '.join(times)

