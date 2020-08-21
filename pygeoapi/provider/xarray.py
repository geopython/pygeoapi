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
                        'axisLabel': self._coverage_properties['time_label'],
                        'lowerBound': self._coverage_properties['bbox'][1],
                        'upperBound': self._coverage_properties['bbox'][3],
                        'uomLabel': self._coverage_properties['bbox_units'],
                        'resolution': self._coverage_properties['resy']
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
                'tags': self._coverage_properties['tags']
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

        for i, dtype, nodataval in zip(self._data.indexes, self._data.dtypes,
                                       self._data.nodatavals):
            LOGGER.debug('Determing rangetype for band {}'.format(i))

            name, units = None, None
            if self._data.units[i-1] is None:
                parameter = _get_parameter_metadata(
                    self._data.profile['driver'], self._data.tags(i))
                name = parameter['description']
                units = parameter['unit_label']

            rangetype['field'].append({
                'id': i,
                'type': 'QuantityType',
                'name': name,
                'definition': dtype,
                'nodata': nodataval,
                'uom': {
                    'id': 'http://www.opengis.net/def/uom/UCUM/{}'.format(
                         units),
                    'type': 'UnitReference',
                    'code': units
                },
                '_meta': {
                    'tags': self._data.tags(i)
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
            range_type = [x for x in ds.variables
                          if len(ds.variables[x].shape) >= 3]

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
                self._data.coords[lon][0], self._data.coords[lon][-1],
                self._data.coords[lat][0], self._data.coords[lat][-1]],
                "driver": "Xarray",
                "height": self._data.dims[lat],
                "width": self._data.dims[lon],
                "time_steps": self._data.dims[time],
                "variables": {var_name:
                                  {key: val for vdict in attrs for
                                   k, v in vdict.items()}
                              for var_name in self._data.variables}
            }

        return gen_covjson(out_meta, data)

    def gen_covjson(self, metadata, data):
        """
        Generate coverage as CoverageJSON representation

        :param metadata: coverage metadata
        :param data: rasterio DatasetReader object

        :returns: dict of CoverageJSON representation
        """

        LOGGER.debug('Creating CoverageJSON domain')
        minx, miny, maxx, maxy = metadata['bbox']

        cj = {
            'type': 'Coverage',
            'domain': {
                'type': 'Domain',
                'domainType': 'Grid',
                'axes': {
                    'x': {
                        'start': minx,
                        'stop': maxx,
                        'num': metadata['width']
                    },
                    'y': {
                        'start': maxy,
                        'stop': miny,
                        'num': metadata['height']
                    }
                },
                'referencing': [{
                    'coordinates': ['x', 'y', 'time'],
                    'system': {
                        'type': self._coverage_properties['crs_type'],
                        'id': self._coverage_properties['bbox_crs']
                    }
                }]
            },
            'parameters': {},
            'ranges': {}
        }

        for bs in bands_select:
            pm = _get_parameter_metadata(
                self._data.profile['driver'], self._data.tags(bs))

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
                    # 'dataType': metadata.dtypes[0],
                    'dataType': 'float',
                    'axisNames': ['y', 'x'],
                    'shape': [metadata['height'], metadata['width']],
                }
                # TODO: deal with multi-band value output
                cj['ranges'][key]['values'] = data.flatten().tolist()
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
                time_var = coord
            if self._data.coords[x].attrs['units'] == 'degrees_north':
                lat_var = coord
            if self._data.coords[x].attrs['units'] == 'degrees_east':
                lon_var = coord

        # It would be preferable to use CF attributes to get width
        # resolution etc but for now a generic approach is used to asess
        # all of the attributes based on lat lon vars
        properties = {
            'bbox': [
                self._data.coords[lon_var][0],
                self._data.bounds[lat_vat][0],
                self._data.coords[lon_var][-1],
                self._data.bounds[lat_vat][-1],
            ],
            'bbox_crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
            'crs_type': 'GeographicCRS',
            'bbox_units': 'deg',
            'x_axis_label': lon_var,
            'y_axis_label': lat_var,
            'time_axis_label': time_var,
            'width': self._data.dims[lon_var],
            'height': self._data.dims[lat_var]
        }

        if 'crs' in self._data.variables.keys():
            properties['bbox_crs'] = '{}/{}'.format(
                'http://www.opengis.net/def/crs/OGC/1.3/',
                self._data.crs.epsg_code)

            properties['inverse_flattening'] = self_data.crs.inverse_flattening
            properties['bbox_units'] = 'degrees'
            properties['resx'] = self._data.attrs['geospatial_lon_units']
            properties['resy'] = self._data.attrs['geospatial_lat_units']
            properties['restime'] = self._data.attrs['time_coverage_resolution']
            properties['crs_type'] = 'ProjectedCRS'

        properties['axes'] = [
            properties['x_axis_label'], properties['y_axis_label']
        ]

        return properties
