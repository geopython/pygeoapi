# =================================================================
#
# Authors: Gregory Petrochenkov <gpetrochenkov@usgs.gov>
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Gregory Petrochenkov
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

import os
import logging
import tempfile
import zipfile

import xarray
import fsspec
import numpy as np

from pygeoapi.provider.base import (BaseProvider,
                                    ProviderConnectionError,
                                    ProviderNoDataError,
                                    ProviderQueryError)
from pygeoapi.util import read_data

LOGGER = logging.getLogger(__name__)


class XarrayProvider(BaseProvider):
    """Xarray Provider"""

    def __init__(self, provider_def):
        """
        Initialize object
        :param provider_def: provider definition
        :returns: pygeoapi.provider.xarray_.XarrayProvider
        """

        super().__init__(provider_def)

        try:
            if provider_def['data'].endswith('.zarr'):
                open_func = xarray.open_zarr
            else:
                if '*' in self.data:
                    LOGGER.debug('Detected multi file dataset')
                    open_func = xarray.open_mfdataset
                else:
                    open_func = xarray.open_dataset
            if provider_def['data'].startswith('s3://'):
                LOGGER.debug('Data is stored in S3 bucket.')
                if 's3' in provider_def.get('options', {}):
                    s3_options = provider_def['options']['s3']
                else:
                    s3_options = {}
                LOGGER.debug(s3_options)
                data_to_open = fsspec.get_mapper(self.data,
                                                 **s3_options)
                LOGGER.debug('Completed S3 Open Function')
            else:
                data_to_open = self.data

            self._data = open_func(data_to_open)
            self._coverage_properties = self._get_coverage_properties()

            self.axes = [self._coverage_properties['x_axis_label'],
                         self._coverage_properties['y_axis_label'],
                         self._coverage_properties['time_axis_label']]

            self.fields = self.get_fields()
        except Exception as err:
            LOGGER.warning(err)
            raise ProviderConnectionError(err)

    def get_fields(self):
        fields = {}

        for key, value in self._data.variables.items():
            if len(value.shape) >= 3:
                LOGGER.debug('Adding variable')
                dtype = value.dtype
                if dtype.name.startswith('float'):
                    dtype = 'number'

                fields[key] = {
                    'type': dtype,
                    'title': value.attrs['long_name'],
                    'x-ogc-unit': value.attrs.get('units')
                }

        return fields

    def query(self, properties=[], subsets={}, bbox=[], bbox_crs=4326,
              datetime_=None, format_='json', **kwargs):
        """
         Extract data from collection collection

        :param properties: list of data variables to return (all if blank)
        :param subsets: dict of subset names with lists of ranges
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param bbox_crs: CRS of bounding box
        :param datetime_: temporal (datestamp or extent)
        :param format_: data format of output

        :returns: coverage data as dict of CoverageJSON or native format
        """

        if not properties and not subsets and format_ != 'json':
            LOGGER.debug('No parameters specified, returning native data')
            if format_ == 'zarr':
                return _get_zarr_data(self._data)
            else:
                return read_data(self.data)

        if len(properties) < 1:
            properties = self.fields.keys()

        data = self._data[[*properties]]

        if any([self._coverage_properties['x_axis_label'] in subsets,
                self._coverage_properties['y_axis_label'] in subsets,
                self._coverage_properties['time_axis_label'] in subsets,
                datetime_ is not None]):

            LOGGER.debug('Creating spatio-temporal subset')

            query_params = {}
            for key, val in subsets.items():
                LOGGER.debug(f'Processing subset: {key}')
                if data.coords[key].values[0] > data.coords[key].values[-1]:
                    LOGGER.debug('Reversing slicing from high to low')
                    query_params[key] = slice(val[1], val[0])
                else:
                    query_params[key] = slice(val[0], val[1])

            if bbox:
                if all([self._coverage_properties['x_axis_label'] in subsets,
                        self._coverage_properties['y_axis_label'] in subsets,
                        len(bbox) > 0]):
                    msg = 'bbox and subsetting by coordinates are exclusive'
                    LOGGER.warning(msg)
                    raise ProviderQueryError(msg)
                else:
                    query_params[self._coverage_properties['x_axis_label']] = \
                        slice(bbox[0], bbox[2])
                    query_params[self._coverage_properties['y_axis_label']] = \
                        slice(bbox[1], bbox[3])

                LOGGER.debug('bbox_crs is not currently handled')

            if datetime_ is not None:
                if self._coverage_properties['time_axis_label'] in subsets:
                    msg = 'datetime and temporal subsetting are exclusive'
                    LOGGER.error(msg)
                    raise ProviderQueryError(msg)
                else:
                    if '/' in datetime_:
                        begin, end = datetime_.split('/')
                        if begin < end:
                            query_params[self.time_field] = slice(begin, end)
                        else:
                            LOGGER.debug('Reversing slicing from high to low')
                            query_params[self.time_field] = slice(end, begin)
                    else:
                        query_params[self.time_field] = datetime_

            LOGGER.debug(f'Query parameters: {query_params}')
            try:
                data = data.sel(query_params)
            except Exception as err:
                LOGGER.warning(err)
                raise ProviderQueryError(err)

        if (any([data.coords[self.x_field].size == 0,
                 data.coords[self.y_field].size == 0,
                 data.coords[self.time_field].size == 0])):
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
            "height": data.sizes[self.y_field],
            "width": data.sizes[self.x_field],
            "time_steps": data.sizes[self.time_field],
            "variables": {var_name: var.attrs
                          for var_name, var in data.variables.items()}
        }

        LOGGER.debug('Serializing data in memory')
        if format_ == 'json':
            LOGGER.debug('Creating output in CoverageJSON')
            return self.gen_covjson(out_meta, data, properties)
        elif format_ == 'zarr':
            LOGGER.debug('Returning data in native zarr format')
            return _get_zarr_data(data)
        else:  # return data in native format
            with tempfile.TemporaryFile() as fp:
                LOGGER.debug('Returning data in native NetCDF format')
                fp.write(data.to_netcdf())
                fp.seek(0)
                return fp.read()

    def gen_covjson(self, metadata, data, fields):
        """
        Generate coverage as CoverageJSON representation

        :param metadata: coverage metadata
        :param data: rasterio DatasetReader object
        :param fields: fields dict

        :returns: dict of CoverageJSON representation
        """

        LOGGER.debug('Creating CoverageJSON domain')
        minx, miny, maxx, maxy = metadata['bbox']
        mint, maxt = metadata['time']

        try:
            tmp_min = data.coords[self.y_field].values[0]
        except IndexError:
            tmp_min = data.coords[self.y_field].values
        try:
            tmp_max = data.coords[self.y_field].values[-1]
        except IndexError:
            tmp_max = data.coords[self.y_field].values

        if tmp_min > tmp_max:
            LOGGER.debug(f'Reversing direction of {self.y_field}')
            miny = tmp_max
            maxy = tmp_min

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

        for key, value in self.fields.items():
            parameter = {
                'type': 'Parameter',
                'description': value['title'],
                'unit': {
                    'symbol': value['x-ogc-unit']
                },
                'observedProperty': {
                    'id': key,
                    'label': {
                        'en': value['title']
                    }
                }
            }

            cj['parameters'][key] = parameter

        data = data.fillna(None)
        data = _convert_float32_to_float64(data)

        try:
            for key, value in self.fields.items():
                cj['ranges'][key] = {
                    'type': 'NdArray',
                    'dataType': value['type'],
                    'axisNames': [
                        'y', 'x', self._coverage_properties['time_axis_label']
                    ],
                    'shape': [metadata['height'],
                              metadata['width'],
                              metadata['time_steps']]
                }
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
            if self._data.coords[coord].attrs.get('units') == 'degrees_north':
                y_var = coord
                continue
            if self._data.coords[coord].attrs.get('units') == 'degrees_east':
                x_var = coord
                continue

        if self.x_field is None:
            self.x_field = x_var
        if self.y_field is None:
            self.y_field = y_var
        if self.time_field is None:
            self.time_field = time_var

        # It would be preferable to use CF attributes to get width
        # resolution etc but for now a generic approach is used to assess
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
            'width': self._data.sizes[self.x_field],
            'height': self._data.sizes[self.y_field],
            'time': self._data.sizes[self.time_field],
            'time_duration': self.get_time_coverage_duration(),
            'bbox_units': 'degrees',
            'resx': np.abs(self._data.coords[self.x_field].values[1]
                           - self._data.coords[self.x_field].values[0]),
            'resy': np.abs(self._data.coords[self.y_field].values[1]
                           - self._data.coords[self.y_field].values[0]),
            'restime': self.get_time_resolution()
        }

        if 'crs' in self._data.variables.keys():
            try:
                properties['bbox_crs'] = f'http://www.opengis.net/def/crs/OGC/1.3/{self._data.crs.epsg_code}'  # noqa

                properties['inverse_flattening'] = self._data.crs.\
                    inverse_flattening

                properties['crs_type'] = 'ProjectedCRS'
            except AttributeError:
                pass

        properties['axes'] = [
            properties['x_axis_label'],
            properties['y_axis_label'],
            properties['time_axis_label']
        ]

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
            'description': attrs.get('long_name'),
            'unit_label': attrs.get('units'),
            'unit_symbol': attrs.get('units'),
            'observed_property_id': name,
            'observed_property_name': attrs.get('long_name')
        }

    def get_time_resolution(self):
        """
        Helper function to derive time resolution
        :returns: time resolution string
        """

        if self._data[self.time_field].size > 1:
            time_diff = (self._data[self.time_field][1] -
                         self._data[self.time_field][0])

            dt = np.array([time_diff.values.astype('timedelta64[{}]'.format(x))
                           for x in ['Y', 'M', 'D', 'h', 'm', 's', 'ms']])

            return str(dt[np.array([x.astype(np.int32) for x in dt]) > 0][0])
        else:
            return None

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

        times = [f'{val} {key}' for key, val
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
    except TypeError as err:
        LOGGER.warning(err)
        if datetime_obj.microsecond != 0:
            value = datetime_obj.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        else:
            value = datetime_obj.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception as err:
        LOGGER.warning(err)
        raise RuntimeError(err)

    return value


def _zip_dir(path, ziph, cwd):
    """
        Convenience function to zip directory with sub directories
        (based on source: https://stackoverflow.com/questions/1855095/)
        :param path: str directory to zip
        :param ziph: zipfile file
        :param cwd: current working directory

        """
    for root, dirs, files in os.walk(path):
        for file in files:

            if len(dirs) < 1:
                new_root = '/'.join(root.split('/')[:-1])
                new_path = os.path.join(root.split('/')[-1], file)
            else:
                new_root = root
                new_path = file

            os.chdir(new_root)
            ziph.write(new_path)
            os.chdir(cwd)


def _get_zarr_data(data):
    """
       Returns bytes to read from Zarr directory zip
       :param data: Xarray dataset of coverage data

       :returns: byte array of zip data
       """

    tmp_dir = tempfile.TemporaryDirectory().name

    zarr_data_filename = f'{tmp_dir}zarr.zarr'
    zarr_zip_filename = f'{tmp_dir}zarr.zarr.zip'

    data.to_zarr(zarr_data_filename, mode='w')

    with zipfile.ZipFile(zarr_zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:  # noqa
        _zip_dir(zarr_data_filename, zipf, os.getcwd())

    with open(zarr_zip_filename, 'rb') as fh:
        return fh.read()


def _convert_float32_to_float64(data):
    """
        Converts DataArray values of float32 to float64
        :param data: Xarray dataset of coverage data

        :returns: Xarray dataset of coverage data
        """

    for var_name in data.variables:
        if data[var_name].dtype == 'float32':
            og_attrs = data[var_name].attrs
            data[var_name] = data[var_name].astype('float64')
            data[var_name].attrs = og_attrs

    return data
