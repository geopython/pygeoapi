# =================================================================
#
# Authors: Adan Butt <Adan.Butt@ec.gc.ca>
#
# Copyright (c) 2023 Adan Butt
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
import os
import sys
import tempfile
import time

import numpy
from pygeoapi.provider.base import (
    BaseProvider,
    ProviderInvalidQueryError,
    ProviderNoDataError
)
from pyproj import CRS, Transformer
from typing import Tuple
import xarray
import zarr

LOGGER = logging.getLogger(__name__)
MAX_DASK_BYTES = 225000


class HRDPSWEonGZarrProvider(BaseProvider):
    """MSC WEonG Zarr provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.base.BaseProvider
        """
        super().__init__(provider_def)

        try:

            self.name = provider_def['name']
            self.type = provider_def['type']
            self.data = provider_def['data']
            self._data = xarray.open_zarr(self.data)
            self._coverage_properties = self._get_coverage_properties()

            # for coverage providers
            self.axes = self._coverage_properties['dimensions']
            self.crs = self._coverage_properties['crs']

        except KeyError:
            raise RuntimeError('name/type/data are required')

        self.editable = provider_def.get('editable', False)
        self.options = provider_def.get('options')
        self.id_field = provider_def.get('id_field')
        self.uri_field = provider_def.get('uri_field')
        self.x_field = provider_def.get('x_field')
        self.y_field = provider_def.get('y_field')
        self.time_field = provider_def.get('time_field')
        self.title_field = provider_def.get('title_field')
        self.properties = provider_def.get('properties', [])
        self.file_types = provider_def.get('file_types', [])
        self.fields = {}
        self.filename = None

    def _get_coverage_properties(self):
        """
        Helper function to normalize coverage properties

        :returns: `dict` of coverage properties
        """
        # Dynammically getting all of the axis names
        all_variables = [i for i in self._data.data_vars]
        the_crs = self._data.attrs.get('CRS', '_CRS')
        self._data = self._data[all_variables[0]]

        all_axis = [i for i in self._data.coords]

        all_dimensions = [i for i in self._data.dims]

        try:
            size_x = float(abs(self._data.rlon[1] - self._data.rlon[0]))
        except IndexError:
            size_x = float(abs(self._data.rlon[0]))

        try:
            size_y = float(abs(self._data.rlat[1] - self._data.rlat[0]))
        except IndexError:
            size_y = float(abs(self._data.rlat[0]))

        properties = {
            # have to convert values to float and int to serilize into json
            'crs': the_crs,
            'axis': all_axis,
            'extent': {
                'minx': float(self._data.rlon.min().values),
                'miny': float(self._data.rlat.min().values),
                'maxx': float(self._data.rlon.max().values),
                'maxy': float(self._data.rlat.max().values),
                'coordinate_reference_system':
                ("http://www.opengis.net/def/crs/ECCC-MSC" +
                    "/-/ob_tran-longlat-weong")
                },
            'size': {
                'width': int(self._data.rlon.size),
                'height': int(self._data.rlat.size)
                },
            'resolution': {
                'x': size_x,
                'y': size_y
                },
            'variables': all_variables,
            'dimensions': all_dimensions
        }

        return properties

    def _get_parameter_metadata(self):
        """
        Helper function to derive parameter name and units
        :returns: dict of parameter metadata
        """
        parameter = {
            'array_dimensons': None,
            'coordinates': None,
            'grid_mapping': None,
            'long_name': None
            }

        parameter['array_dimensons'] = self._data.dims
        parameter['coordinates'] = self._data.coords
        parameter['grid_mapping'] = (
            self._data.attrs['grid_mapping'])
        parameter['units'] = self._data.attrs['units']
        parameter['long_name'] = self._data.attrs['long_name']
        parameter['id'] = self._data.attrs['nomvar'],
        parameter['data_type'] = self._data.dtype

        return parameter

    def get_coverage_domainset(self):
        """
        Provide coverage domainset

        :returns: CIS JSON object of domainset metadata
        'CIS JSON':https://docs.opengeospatial.org/is/09-146r6/09-146r6.html#46
        """
        a = _gen_domain_axis(self, data=self._data)
        sr = self._coverage_properties['extent']['coordinate_reference_system']
        w = self._coverage_properties['size']['width']
        h = self._coverage_properties['size']['height']

        domainset = {
            'type': 'DomainSetType',
            'generalGrid': {
                'type': 'GeneralGridCoverageType',
                'srsName': sr,
                'axisLabels': a[1],
                'axis': a[0],
                'gridLimits': {
                    'type': 'GridLimitsType',
                    'srsName': sr,
                    'axisLabels': ['i', 'j'],
                    'axis': [
                                {
                                    "type": 'IndexAxisType',
                                    "axisLabel": 'i',
                                    "lowerBound": 0,
                                    "upperBound": w
                                },
                                {
                                    "type": 'IndexAxisType',
                                    "axisLabel": 'j',
                                    "lowerBound": 0,
                                    "upperBound": h
                                }
                            ],
                    }

                }
            }

        return domainset

    def get_coverage_rangetype(self):
        """
        Provide coverage rangetype

        :returns: CIS JSON object of rangetype metadata
        'CIS JSON':https://docs.opengeospatial.org/is/09-146r6/09-146r6.html#46
        """
        # at 0, we are dealing with one variable (1 zarr file per variable)
        parameter_metadata = self._get_parameter_metadata()

        rangetype = {
            'type': 'DataRecordType',
            'field': [
                {
                    'id': parameter_metadata['id'][0],
                    'type': 'QuantityType',
                    'name': parameter_metadata['long_name'],
                    'encodingInfo': {
                        'dataType': str(parameter_metadata['data_type'])
                    },
                    'definition': parameter_metadata['units'],
                    'uom': {
                        'type': 'UnitReferenceType',
                        'code': parameter_metadata['units']
                    }
                }
            ]
        }

        return rangetype

    def query(self, bbox=[], datetime_=None, subsets={}, format_="json"):
        """
        query the provider

        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime: temporal (datestamp or extent)
        :param format_: data format of output

        :returns: dict of 0..n GeoJSON features or coverage data
        #TODO: antimeridian bbox
        """

        var_dims = self._coverage_properties['dimensions']
        query_return = {}
        if not subsets and not bbox and datetime_ is None:
            for i in reversed(range(1, 2)):
                for dim in var_dims:
                    query_return[dim] = i
                data_vals = self._data.head(**query_return)
                if format_ == 'zarr':
                    new_dataset = data_vals.to_dataset()
                    new_dataset.attrs['_CRS'] = self.crs
                    return _get_zarr_data_stream(new_dataset)
                elif data_vals.data.nbytes < MAX_DASK_BYTES:
                    return _gen_covjson(self, the_data=data_vals)
        else:
            if subsets:
                for dim, value in subsets.items():
                    if dim in var_dims:
                        if (
                            len(value) == 2 and
                            isinstance(value[0], (int, float)) and
                            isinstance(value[1], (int, float))
                        ):
                            query_return[dim] = slice(value[0], value[1])

                        else:
                            msg = 'values must be well-defined range'
                            LOGGER.error(msg)
                            raise ProviderInvalidQueryError(msg)

                    else:  # redundant check (done in api.py)
                        msg = f'Invalid Dimension (Dimension {dim} not found)'
                        LOGGER.error(msg)
                        raise ProviderInvalidQueryError(msg)

            if bbox:
                if 'rlat' in query_return or 'rlon' in query_return:
                    msg = (
                          'Invalid subset' +
                          '(Cannot subset by both "rlat", "rlon" and "bbox")'
                    )
                    LOGGER.error(msg)
                    raise ProviderInvalidQueryError(msg)
                else:
                    query_return['rlat'] = slice(bbox[1], bbox[3])
                    query_return['rlon'] = slice(bbox[0], bbox[2])

            if 'rlat' in query_return and 'rlon' in query_return:
                max_sub, min_sub = _convert_subset_to_crs(
                    query_return['rlat'], query_return['rlon'], self.crs
                    )
                query_return['rlat'] = slice(min_sub[1], max_sub[1])
                query_return['rlon'] = slice(min_sub[0], max_sub[0])

            if datetime_:
                if '/' not in datetime_:  # single date
                    query_return['time'] = slice(datetime_, datetime_)

                else:
                    start_date = datetime_.split('/')[0]
                    end_date = datetime_.split('/')[1]
                    query_return['time'] = slice(start_date, end_date)
        LOGGER.debug(f'query_return: {query_return}')

        try:
            if all([query_return['rlat'].start != query_return['rlat'].stop,
                    query_return['rlon'].start != query_return['rlon'].stop]):
                LOGGER.info('Spatial subset query')
                LOGGER.debug(f'Rlat start {query_return["rlat"].start}')
                LOGGER.debug(f'Rlat stop {query_return["rlat"].stop}')
                data_vals = self._data.sel(**query_return)
            else:
                single_query = {}
                new_query = {}
                try:
                    if query_return['rlat'].start == query_return['rlat'].stop:
                        single_query['rlat'] = query_return['rlat'].start
                    else:
                        single_query['nolat'] = '0'
                    if query_return['rlon'].start == query_return['rlon'].stop:
                        single_query['rlon'] = query_return['rlon'].start
                    else:
                        single_query['nolon'] = '0'
                    if ('nolat' and 'nolon') not in single_query:
                        LOGGER.info(f'Nearest point query: {single_query}')
                        data_vals = self._data.sel(
                            **single_query, method='nearest')
                        new_rlon = data_vals.rlon.values
                        new_rlat = data_vals.rlat.values
                        LOGGER.info(
                            f'Nearest point returned: {new_rlon}, {new_rlat}')
                        LOGGER.debug(f'NEAREST DATA: {data_vals}')
                    elif 'nolat' in single_query:
                        data_vals = self._data.sel(
                            rlon=single_query['rlon'], method='nearest')
                        new_rlon = data_vals.rlon.values
                        LOGGER.debug(f'New rlon: {new_rlon}')
                        single_query.pop('nolat')
                        single_query['rlon'] = slice(new_rlon, new_rlon)
                    elif 'nolon' in single_query:
                        data_vals = self._data.sel(
                            rlat=single_query['rlat'], method='nearest')
                        new_rlat = data_vals.rlat.values
                        LOGGER.debug(f'New rlat: {new_rlat}')
                        single_query.pop('nolon')
                        single_query['rlat'] = slice(new_rlat, new_rlat)

                    else:
                        LOGGER.debug('Reseting query')
                        single_query = {}
                except Exception as e:
                    msg = f'Nearest point query failed: {e}'
                    LOGGER.error(msg)
                    raise ProviderNoDataError(msg)
                LOGGER.info('Nearest point query')
                for key in query_return.keys():
                    if query_return[key].start == query_return[key].stop:
                        single_query[key] = query_return[key].start
                    else:
                        new_query[key] = query_return[key]
                LOGGER.debug(f'Nearest point returned: {single_query}')
                data_vals = self._data.sel(**single_query, method='nearest')
                LOGGER.debug(f'Nearest point returned DIMS: {data_vals}')
                data_vals = data_vals.sel(**new_query)
                LOGGER.debug(f'FINAL data_vals: {data_vals}')

        except Exception as e:
            # most likely invalid time or subset value
            msg = f'Invalid query: No data found {e}'
            LOGGER.error(msg)
            raise ProviderNoDataError(msg)

        if data_vals.values.size == 0:
            msg = 'Invalid query: No data found'
            LOGGER.error(msg)
            raise ProviderNoDataError(msg)

        if format_ == 'zarr':
            new_dataset = data_vals.to_dataset()
            new_dataset.attrs['_CRS'] = self.crs
            return _get_zarr_data_stream(new_dataset)

        if data_vals.data.nbytes > MAX_DASK_BYTES:
            raise ProviderInvalidQueryError(
                'Data size exceeds maximum allowed size'
                )

        return _gen_covjson(self, the_data=data_vals)

    def __repr__(self):
        return '<BaseProvider> {}'.format(self.type)


def _get_zarr_data_stream(data):
    """
    Helper function to convert a xarray dataset to zip file in memory

    :param data: Xarray dataset of coverage data

    :returns: bytes of zip (zarr) data
    """

    mem_bytes = (
        (os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')) * 0.75
        )

    try:
        with tempfile.SpooledTemporaryFile(
            max_size=int((mem_bytes*mem_bytes)+1), suffix='zip'
        ) as f:
            with tempfile.NamedTemporaryFile() as f2:
                data.to_zarr(zarr.ZipStore(f2.name), mode='w')
                return f2.read()
            LOGGER.info(f'satisfy flake8 tests, there is no need to use {f}')
    except Exception:
        raise ProviderInvalidQueryError(
            'Data size is too large to be processed'
        )


def _gen_domain_axis(self, data):
    """
    Helper function to generate domain axis

    :param data: Xarray dataset of coverage data

    :returns: list of dict of domain axis
    """

    # Dynammically getting all of the axis names
    all_axis = []
    for coord in data.dims:
        all_axis.append(coord)

    # Makes sure axis are in the correct order
    j, k = all_axis.index('rlon'), all_axis.index(all_axis[0])
    all_axis[j], all_axis[k] = all_axis[k], all_axis[j]

    j, k = all_axis.index('rlat'), all_axis.index(all_axis[1])
    all_axis[j], all_axis[k] = all_axis[k], all_axis[j]

    all_dims = []
    for dim in data.dims:
        all_dims.append(dim)

    j, k = all_dims.index('rlon'), all_dims.index(all_dims[0])
    all_dims[j], all_dims[k] = all_dims[k], all_dims[j]

    j, k = all_dims.index('rlat'), all_dims.index(all_dims[1])
    all_dims[j], all_dims[k] = all_dims[k], all_dims[j]

    aa = []

    for a, dim in zip(all_axis, all_dims):
        if a == 'time':
            res = ''.join(c for c in (
                str(data[dim].values[1] - data[dim].values[0]))
                if c.isdigit())
            uom = ''.join(c for c in (
                str(data[dim].values[1] - data[dim].values[0]))
                if not c.isdigit())
            aa.append(
                {
                    'type': 'RegularAxisType',
                    'axisLabel': a,
                    'lowerBound': str(data[dim].min().values),
                    'upperBound': str(data[dim].max().values),
                    'uomLabel': uom.strip(),
                    'resolution': float(res)
                })

        else:
            try:
                uom = self._data[dim].attrs['units']
            except KeyError:
                uom = 'n/a'

            try:
                rez = float(abs(data[dim].values[1] - data[dim].values[0]))
            except IndexError:
                rez = float(abs(data[dim].values[0]))
            aa.append(
                {
                    'type': 'RegularAxisType',
                    'axisLabel': a,
                    'lowerBound': float(data[dim].min().values),
                    'upperBound': float(data[dim].max().values),
                    'uomLabel': uom,
                    'resolution': rez
                })
    return aa, all_dims


def _convert_subset_to_crs(new_lat: slice, new_lon: slice, crs) -> Tuple:
    """
    Helper function to convert a rlat and rlon values
    from WGS84 to a native crs

    :param new_lat: rlat slice
    :param new_lon: rlon slice
    :param crs: CRS to convert to

    :returns: max and min subset of rlat and rlon in native crs
    """
    crs_src = CRS.from_epsg(4326)
    crs_dst = CRS.from_wkt(crs)
    to_transform = Transformer.from_crs(crs_src, crs_dst, always_xy=True)
    max_sub = to_transform.transform(new_lon.stop, new_lat.stop)
    min_sub = to_transform.transform(new_lon.start, new_lat.start)
    LOGGER.debug(f'Max subset: {max_sub}, Min subset: {min_sub}')
    return max_sub, min_sub


def _gen_covjson(self, the_data):
    """
    Helper function to Generate coverage as CoverageJSON representation

    :param the_data: xarray dataArray from query

    :returns: dict of CoverageJSON representation
    """

    LOGGER.info('Creating CoverageJSON domain')
    numpy.set_printoptions(threshold=sys.maxsize)
    props = self._coverage_properties
    parameter_metadata = self._get_parameter_metadata()

    cov_json = {
        'type': 'CoverageType',
        'domain': {
            'type': 'DomainType',
            'domainType': 'Grid',
            'axes': {
                'x': {
                    'start': float(the_data.rlon.min().values),
                    'stop': float(the_data.rlon.max().values),
                    'num': int(the_data.rlon.size)
                },
                'y': {
                    'start': float(the_data.rlat.min().values),
                    'stop': float(the_data.rlat.max().values),
                    'num': int(the_data.rlat.size)
                },
                't': {
                    'start': str(the_data.time.min().values),
                    'stop': str(the_data.time.max().values),
                    'num': int(the_data.time.size)
                }
            },
            'referencing': [{
                'coordinates': ['x', 'y'],
                'system': {
                    'type': 'GeographicCRS',
                    'id': props['extent']['coordinate_reference_system']
                }
            }]
        }
    }

    parameter = {
        parameter_metadata['id'][0]: {
            'type': 'Parameter',
            'description': {
                'en': parameter_metadata['long_name']
            },
            'unit': {
                'symbol': parameter_metadata['units']
            },
            'observedProperty': {
                'id': parameter_metadata['id'][0],
                'label': {
                    'en': parameter_metadata['long_name']
                }
            }
        }
    }

    cov_json['parameters'] = parameter

    the_range = {
        parameter_metadata['id'][0]: {
                                        'type': 'NdArray',
                                        'dataType': str(the_data.dtype),
                                        'axisNames': the_data.dims,
                                        'shape': the_data.shape
                                        }
    }

    if 0 in the_data.shape:
        raise ProviderInvalidQueryError(
            'No data found. Pass in correct (exact) parameters.'
        )

    else:
        the_range[parameter_metadata['id'][0]]['values'] = (
                the_data.data.flatten().compute().data.tolist()
            )

    cov_json['ranges'] = the_range

    LOGGER.debug(cov_json)

    return cov_json