# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
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

import rasterio
from rasterio.windows import from_bounds

from pygeoapi.provider.base import (BaseProvider, ProviderConnectionError,
                                    ProviderQueryError)

LOGGER = logging.getLogger(__name__)


class RasterioProvider(BaseProvider):
    """Rasterio Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.providers.rasterio_.RasterioProvider
        """

        BaseProvider.__init__(self, provider_def)

        try:
            self.d = rasterio.open(self.data)
        except Exception as err:
            LOGGER.warning(err)
            raise ProviderConnectionError(err)

    def get_coverage(self):
        metadata = {}
        axes = self._get_axes()
        range_type = self._get_range_type()
        metadata['envelope'] = {
            'type': 'EnvelopeByAxisType',
            'id': 'envelope',
            'srsName': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
            'axisLabels': list({k for d in axes for k in d.keys()}),
            'axis': axes,
            'rangeType': range_type
        }

        return metadata

    def get_metadata(self):
        metadata = {
            'bounds': self.d.bounds,
            'meta': self.d.meta,
            'tags': self.d.tags()
        }

        return metadata

    def query(self, bands=[], subsets={}):

        args = {}

        if bands:
            args['indexes'] = list(map(int, bands))

        if 'lat' in subsets and 'long' in subsets:
            LOGGER.debug('Creating window')

            window = from_bounds(
                transform=self.d.transform,
                left=subsets['long'][0],
                bottom=subsets['lat'][0],
                right=subsets['long'][1],
                top=subsets['lat'][1]
            )
            LOGGER.debug('window: {}'.format(window))
            args['window'] = window

        try:
            return self.d.read(**args).tolist()
        except Exception as err:
            LOGGER.warning(err)
            raise ProviderQueryError(err)

    def _get_range_type(self):
        rt = {
            'type': 'DataRecordType',
            'field': {
                'type': 'QuantityType',
                'definition': self.d.meta['dtype'],
            }
        }
        return rt

    def _get_axes(self):
        axes = []
        axes_keys = []
        tags = self.d.tags()
        for key, value in tags.items():
            if not key.startswith(('NETCDF', 'NC_GLOBAL')):
                axis_key = key.split('#')[0]
                if all([axis_key not in axes_keys and
                       '{}#axis'.format(axis_key) in tags]):  # envelope
                    axes_keys.append(axis_key)
                    axis_metadata = {}
                    axis_metadata[axis_key] = {
                        'id': 'envelope_{}'.format(axis_key),
                        'type': 'AxisExtentType',
                        'axisLabel': tags['{}#standard_name'.format(axis_key)],
                        'uomLabel': tags['{}#units'.format(axis_key)],
                    }
                    if axis_key == 'lat':
                        axis_metadata[axis_key] = {
                            'lowerBound': self.d.bounds.bottom,
                            'upperBound': self.d.bounds.top
                        }
                    elif axis_key == 'lon':
                        axis_metadata[axis_key] = {
                            'lowerBound': self.d.bounds.left,
                            'upperBound': self.d.bounds.right
                        }

                    axes.append(axis_metadata)

        if 'NETCDF_DIM_EXTRA' in tags:
            dims = _netcdflist2list(tags['NETCDF_DIM_EXTRA'])
            for dim in dims:
                dim_values_tag = 'NETCDF_DIM_{}_VALUES'.format(dim)
                dim_values = _netcdflist2list(tags[dim_values_tag])

                for axis in axes:
                    if dim in axis:
                        axis[dim]['lowerBound'] = min(dim_values)
                        axis[dim]['upperBound'] = max(dim_values)

        return axes


def _netcdflist2list(tag):
    return tag.replace('{', '').replace('}', '').split(',')
