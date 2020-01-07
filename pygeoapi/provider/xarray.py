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

        if os.path.exists(self.data):
            idx = self.data.rfind('.')
            data_type = self.data[idx:]
            if data_type == '.zarr':
                self.d = xarray.open_zarr(self.data)
            else:
                try:
                    self.d = xarray.open_dataset(self.data)
                except TypeError:
                    LOGGER.warning(TypeError)
                    raise ProviderConnectionError(TypeError)

        else:
            try:
                self.d = xarray.open_dataset(self.data)
            except:
                self.d = None

    def get_coverage(self):

        metadata = {}
        axes = self._get_axes()
        metadata['envelope'] = {
            'type': 'EnvelopeByAxisType',
            'id': 'envelope',
            'srsName': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
            'axisLabels': list({k for d in axes for k in d.keys()}),
            'axis': axes
        }

        return metadata

    def get_metadata(self):

        if self.d is None:
            LOGGER.warning(ValueError)
            raise ProviderConnectionError(ValueError)

        metadata = {}

        metadata['bounds'] = [
            self.d.attrs['geospatial_lon_min'], self.d.attrs['geospatial_lat_min'],
            self.d.attrs['geospatial_lon_max'], self.d.attrs['geospatial_lat_max']
        ]
        metadata['meta'] = self.data.attrs
        metadata['tags'] = ''

        return metadata

    def query(self, range_subset=[], bbox=[-20,-20,20,20]):
        """
        query the provider by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """

        args = {}

        if range_subset:
            args['indexes'] = range_subset


        # try:
        if len(range_subset) > 0:
            data = self.d[[*range_subset]]
        else:
            data = self.d


        # try:
        #     bounds = [data['lon'],
        #              data['lat'],
        #              data['lon'],
        #              data['lat']]
        # except:
        #     bounds = [data['Longitude'],
        #               data['Latitude'],
        #               data['Longitude'],
        #               data['Latitude']]
        #
        #
        # data = data.where(bounds[0] < bbox[0])
        # data = data.where(bounds[1] < bbox[1])
        # data = data.where(bounds[2] > bbox[2])
        # data = data.where(bounds[3] > bbox[3])

        # except Exception as err:
        #     LOGGER.warning(err)
        #     raise ProviderQueryError(err)

        return data.to_array().values.tolist()
