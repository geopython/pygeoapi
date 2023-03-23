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
"""Plugin loader"""

import importlib
import logging
from typing import Any

LOGGER = logging.getLogger(__name__)

#: Loads provider plugins to be used by pygeoapi,\
#: formatters and processes available
PLUGINS = {
    'provider': {
        'CSV': 'pygeoapi.provider.csv_.CSVProvider',
        'Elasticsearch': 'pygeoapi.provider.elasticsearch_.ElasticsearchProvider',  # noqa
        'ElasticsearchCatalogue': 'pygeoapi.provider.elasticsearch_.ElasticsearchCatalogueProvider',  # noqa
        'ESRI': 'pygeoapi.provider.esri.ESRIServiceProvider',
        'GeoJSON': 'pygeoapi.provider.geojson.GeoJSONProvider',
        'OGR': 'pygeoapi.provider.ogr.OGRProvider',
        'PostgreSQL': 'pygeoapi.provider.postgresql.PostgreSQLProvider',
        'SQLiteGPKG': 'pygeoapi.provider.sqlite.SQLiteGPKGProvider',
        'MongoDB': 'pygeoapi.provider.mongo.MongoProvider',
        'FileSystem': 'pygeoapi.provider.filesystem.FileSystemProvider',
        'Hateoas': 'pygeoapi.provider.hateoas.HateoasProvider',
        'rasterio': 'pygeoapi.provider.rasterio_.RasterioProvider',
        'xarray': 'pygeoapi.provider.xarray_.XarrayProvider',
        'MapScript': 'pygeoapi.provider.mapscript_.MapScriptProvider',
        'WMSFacade': 'pygeoapi.provider.wms_facade.WMSFacadeProvider',
        'MVT': 'pygeoapi.provider.mvt.MVTProvider',
        'TinyDBCatalogue': 'pygeoapi.provider.tinydb_.TinyDBCatalogueProvider',
        'SensorThings': 'pygeoapi.provider.sensorthings.SensorThingsProvider',
        'Socrata': 'pygeoapi.provider.socrata.SODAServiceProvider',
        'xarray-edr': 'pygeoapi.provider.xarray_edr.XarrayEDRProvider'
    },
    'formatter': {
        'CSV': 'pygeoapi.formatter.csv_.CSVFormatter'
    },
    'process': {
        'HelloWorld': 'pygeoapi.process.hello_world.HelloWorldProcessor'
    },
    'process_manager': {
        'Dummy': 'pygeoapi.process.manager.dummy.DummyManager',
        'TinyDB': 'pygeoapi.process.manager.tinydb_.TinyDBManager',
        'MongoDB': 'pygeoapi.process.manager.mongodb_.MongoDBManager'
    }
}


def load_plugin(plugin_type: str, plugin_def: dict) -> Any:
    """
    loads plugin by name

    :param plugin_type: type of plugin (provider, formatter)
    :param plugin_def: plugin definition

    :returns: plugin object
    """

    name = plugin_def['name']

    if plugin_type not in PLUGINS.keys():
        msg = f'Plugin type {plugin_type} not found'
        LOGGER.exception(msg)
        raise InvalidPluginError(msg)

    plugin_list = PLUGINS[plugin_type]

    LOGGER.debug(f'Plugins: {plugin_list}')

    if '.' not in name and name not in plugin_list.keys():
        msg = f'Plugin {name} not found'
        LOGGER.exception(msg)
        raise InvalidPluginError(msg)

    if '.' in name:  # dotted path
        packagename, classname = name.rsplit('.', 1)
    else:  # core formatter
        packagename, classname = plugin_list[name].rsplit('.', 1)

    LOGGER.debug(f'package name: {packagename}')
    LOGGER.debug(f'class name: {classname}')

    module = importlib.import_module(packagename)
    class_ = getattr(module, classname)
    plugin = class_(plugin_def)

    return plugin


class InvalidPluginError(Exception):
    """Invalid plugin"""
    pass
