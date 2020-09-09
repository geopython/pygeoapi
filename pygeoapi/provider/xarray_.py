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

import logging
import tempfile

import xarray
import numpy as np

from pygeoapi.provider.base import (BaseProvider,
                                    ProviderConnectionError,
                                    ProviderNoDataError,
                                    ProviderQueryError)

LOGGER = logging.getLogger(__name__)


class XarrayProvider(BaseProvider):
    """Xarray Provider"""

    def __init__(self, provider_def):
        """
        Initialize object
        :param provider_def: provider definition
        :returns: pygeoapi.providers.xarray_.XarrayProvider
        """

        BaseProvider.__init__(self, provider_def)

        try:
            self._data = xarray.open_dataset(self.data)
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

        c_props = self._coverage_properties
        domainset = {
            'type': 'DomainSetType',
            'generalGrid': {
                'type': 'GeneralGridCoverageType',
                'srsName': c_props['bbox_crs'],
                'axisLabels': [
                    c_props['x_axis_label'],
                    c_props['y_axis_label']
                ],
                'axis': [{
                    'type': 'RegularAxisType',
                    'axisLabel': c_props['x_axis_label'],
                    'lowerBound': c_props['bbox'][0],
                    'upperBound': c_props['bbox'][2],
                    'uomLabel': c_props['bbox_units'],
                    'resolution': c_props['resx']
                }, {
                    'type': 'RegularAxisType',
                    'axisLabel': c_props['y_axis_label'],
                    'lowerBound': c_props['bbox'][1],
                    'upperBound': c_props['bbox'][3],
                    'uomLabel': c_props['bbox_units'],
                    'resolution': c_props['resy']
                },
                    {
                        'type': 'RegularAxisType',
                        'axisLabel': c_props['time_axis_label'],
                        'lowerBound': c_props['time_range'][0],
                        'upperBound': c_props['time_range'][1],
                        'uomLabel': c_props['restime'],
                        'resolution': c_props['restime']
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
                        'upperBound': c_props['width']
                    }, {
                        'type': 'IndexAxisType',
                        'axisLabel': 'j',
                        'lowerBound': 0,
                        'upperBound': c_props['height']
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

    def query(self, range_subset=[], subsets={}, format_='json'):
        """
         Extract data from collection collection

        :param range_subset: list of data variables to return (all if blank)
        :param subsets: dict of subset names with lists of ranges
        :param format_: data format of output

        :returns: coverage data as dict of CoverageJSON or native format
        """

        if len(range_subset) < 1:
            range_subset = self.fields

        data = self._data[[*range_subset]]

        if(self._coverage_properties['x_axis_label'] in subsets or
           self._coverage_properties['y_axis_label'] in subsets or
           self._coverage_properties['time_axis_label'] in subsets):

            LOGGER.debug('Creating spatio-temporal subset')

            query_params = {}
            for key, val in subsets.items():
                if data.coords[key].values[0] > data.coords[key].values[-1]:
                    LOGGER.debug('Reversing slicing low/high')
                    query_params[key] = slice(val[1], val[0])
                else:
                    query_params[key] = slice(val[0], val[1])

            LOGGER.debug('Query parameters: {}'.format(query_params))
            try:
                data = data.sel(query_params)
            except Exception as err:
                LOGGER.warning(err)
                raise ProviderQueryError(err)

        subsets_data_total = 0
        for key, val in subsets.items():
            subsets_data_total += data.coords[key].size

        if subsets_data_total == 0:
            msg = 'No data found'
            LOGGER.warning(msg)
            raise ProviderNoDataError(msg)

        out_meta = {
            'bbox': [
                data.coords[self.x_field].values[0],
                data.coords[self.y_field].values[0],
                data.coords[self.x_field].values[-1],
                data.coords[self.y_field].values[-1]
            ],
            "time": [
                _to_datetime_string(data.coords[self.time_field].values[0]),
                _to_datetime_string(data.coords[self.time_field].values[-1])
            ],
            "driver": "xarray",
            "height": data.dims[self.y_field],
            "width": data.dims[self.x_field],
            "time_steps": data.dims[self.time_field],
            "variables": {var_name: var.attrs
                          for var_name, var in data.variables.items()}
        }

        LOGGER.debug('Serializing data in memory')
        if format_ == 'json':
            LOGGER.debug('Creating output in CoverageJSON')
            return self.gen_covjson(out_meta, data, range_subset)

        else:  # return data in native format
            with tempfile.TemporaryFile() as fp:
                LOGGER.debug('Returning data in native format')
                fp.write(data.to_netcdf())
                fp.seek(0)
                return fp.read()

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

        if data.coords[self.y_field].values[0] > data.coords[self.y_field].values[-1]:  # noqa
            LOGGER.debug('Reversing direction of {}'.format(self.y_field))
            miny = data.coords[self.y_field].values[-1]
            maxy = data.coords[self.y_field].values[0]

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
                    },
                    self.time_field: {
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
                    'axisNames': [
                        'y', 'x', self._coverage_properties['time_axis_label']
                    ],
                    'shape': [metadata['height'],
                              metadata['width'],
                              metadata['time_steps']]
                }

                data = data.fillna(None)
                cj['ranges'][key]['values'] = data[key].values.flatten().tolist()  # noqa
        except IndexError as err:
            LOGGER.warning(err)
            raise ProviderQueryError('Invalid query parameter')

        return cj

    def _get_coverage_properties(self):
        """
        Helper function to normalize coverage properties

        :returns: `dict` of coverage properties
        """

        time_var, y_var, x_var = [None, None, None]
        for coord in self._data.coords:
            if coord.lower() == 'time':
                time_var = coord
                continue
            if self._data.coords[coord].attrs['units'] == 'degrees_north':
                y_var = coord
                continue
            if self._data.coords[coord].attrs['units'] == 'degrees_east':
                x_var = coord
                continue

        if self.x_field is None:
            self.x_field = x_var
        if self.y_field is None:
            self.y_field = y_var
        if self.time_field is None:
            self.time_field = time_var

        # It would be preferable to use CF attributes to get width
        # resolution etc but for now a generic approach is used to asess
        # all of the attributes based on lat lon vars

        properties = {
            'bbox': [
                self._data.coords[self.x_field].values[0],
                self._data.coords[self.y_field].values[0],
                self._data.coords[self.x_field].values[-1],
                self._data.coords[self.y_field].values[-1],
            ],
            'time_range': [
                _to_datetime_string(
                    self._data.coords[self.time_field].values[0]
                ),
                _to_datetime_string(
                    self._data.coords[self.time_field].values[-1]
                )
            ],
            'bbox_crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
            'crs_type': 'GeographicCRS',
            'x_axis_label': self.x_field,
            'y_axis_label': self.y_field,
            'time_axis_label': self.time_field,
            'width': self._data.dims[self.x_field],
            'height': self._data.dims[self.y_field],
            'time': self._data.dims[self.time_field],
            'time_duration': self.get_time_coverage_duration(),
            'bbox_units': 'degrees',
            'resx': np.abs(self._data.coords[self.x_field].values[1]
                           - self._data.coords[self.x_field].values[0]),
            'resy': np.abs(self._data.coords[self.y_field].values[1]
                           - self._data.coords[self.y_field].values[0]),
            'restime': self.get_time_resolution()
        }

        if 'crs' in self._data.variables.keys():
            properties['bbox_crs'] = '{}/{}'.format(
                'http://www.opengis.net/def/crs/OGC/1.3/',
                self._data.crs.epsg_code)

            properties['inverse_flattening'] = self._data.crs.\
                inverse_flattening

            properties['crs_type'] = 'ProjectedCRS'

        properties['axes'] = [
            properties['x_axis_label'],
            properties['y_axis_label'],
            properties['time_axis_label']
        ]

        properties['fields'] = [name for name in self._data.variables
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
            'description': attrs.get('long_name', None),
            'unit_label': attrs.get('units', None),
            'unit_symbol': attrs.get('units', None),
            'observed_property_id': name,
            'observed_property_name': attrs.get('long_name', None)
        }

    def get_time_resolution(self):
        """
        Helper function to derive time resolution
        :returns: time resolution string
        """

        time_diff = (self._data[self.time_field][1] -
                     self._data[self.time_field][0])

        dts = np.array([time_diff.values.astype('timedelta64[{}]'.format(x))
                       for x in ['Y', 'M', 'D', 'h', 'm', 's', 'ms']])

        return str(dts[np.array([x.astype(np.int) for x in dts]) > 0][0])

    def get_time_coverage_duration(self):
        """
        Helper function to derive time coverage duration
        :returns: time coverage duration string
        """

        dur = self._data[self.time_field][-1] - self._data[self.time_field][0]
        ms_difference = dur.values.astype('timedelta64[ms]').astype(np.double)

        time_dict = {
            'days': int(ms_difference / 1000 / 60 / 60 / 24),
            'hours': int((ms_difference / 1000 / 60 / 60) % 24),
            'minutes': int((ms_difference / 1000 / 60) % 60),
            'seconds': int(ms_difference / 1000) % 60
        }

        times = ['{} {}'.format(val, key) for key, val
                 in time_dict.items() if val > 0]

        return ', '.join(times)


def _to_datetime_string(datetime_obj):
    """
    Convenience function to formulate string from various datetime objects

    :param datetime_obj: datetime object (native datetime, cftime)

    :returns: str representation of datetime
    """

    try:
        value = np.datetime_as_string(datetime_obj)
    except Exception as err:
        LOGGER.warning(err)
        value = datetime_obj.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    return value
