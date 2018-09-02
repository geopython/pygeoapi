# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2018 Tom Kralidis
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

import importlib
import logging

LOGGER = logging.getLogger(__name__)

PROVIDERS = {
    'CSV': 'pygeoapi.provider.csv_.CSVProvider',
    'Elasticsearch': 'pygeoapi.provider.elasticsearch_.ElasticsearchProvider',
    'GeoJSON': 'pygeoapi.provider.geojson.GeoJSONProvider',
    'SQLite': 'pygeoapi.provider.sqlite.SQLiteProvider',
    'GeoPackage': 'pygeoapi.provider.geopackage.GeoPackageProvider'
}


def load_provider(provider_def):
    """
    loads provider by name

    :param provider_def: provider definition

    :returns: provider object
    """

    LOGGER.debug('Providers: {}'.format(PROVIDERS))

    pname = provider_def['name']

    if '.' not in pname and pname not in PROVIDERS.keys():
        msg = 'Provider {} not found'.format(pname)
        LOGGER.exception(msg)
        raise InvalidProviderError(msg)

    if '.' in pname:  # dotted path
        packagename, classname = pname.rsplit('.', 1)
    else:  # core provider
        packagename, classname = PROVIDERS[pname].rsplit('.', 1)

    LOGGER.debug('package name: {}'.format(packagename))
    LOGGER.debug('class name: {}'.format(classname))

    module = importlib.import_module(packagename)
    class_ = getattr(module, classname)
    provider = class_(provider_def)
    return provider


class InvalidProviderError(Exception):
    """invalid provider"""
    pass
