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

        self.d = rasterio.open(self.data)

    def get_metadata(self):
        metadata = {}

        metadata['bounds'] = [self.d.bounds.left, self.d.bounds.bottom, self.d.bounds.right, self.d.bounds.top]
        metadata['name'] = self.d.name
        metadata['bands'] = self.d.count
        metadata['width'] = self.d.width
        metadata['height'] = self.d.height
        metadata['resx'] = self.d.res[0]
        metadata['resy'] = self.d.res[1]
        metadata['native_format'] = self.d.driver

        metadata['transform'] = [
            self.d.transform.a,
            self.d.transform.b,
            self.d.transform.c,
            self.d.transform.d,
            self.d.transform.e,
            self.d.transform.f
        ]

        return metadata
