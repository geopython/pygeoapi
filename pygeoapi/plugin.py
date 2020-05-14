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
"""Plugin loader"""

import importlib
import logging
import os

LOGGER = logging.getLogger(__name__)

#: Loads provider plugins to be used by pygeoapi,\
#: formatters and processes available
PLUGINS = {
    'provider': {
        'CSV': 'pygeoapi.provider.csv_.CSVProvider',
        'Elasticsearch': 'pygeoapi.provider.elasticsearch_.ElasticsearchProvider',  # noqa
        'GeoJSON': 'pygeoapi.provider.geojson.GeoJSONProvider',
        'OGR': 'pygeoapi.provider.ogr.OGRProvider',
        'PostgreSQL': 'pygeoapi.provider.postgresql.PostgreSQLProvider',
        'SQLiteGPKG': 'pygeoapi.provider.sqlite.SQLiteGPKGProvider',
        'MongoDB': 'pygeoapi.provider.mongo.MongoProvider',
        'FileSystem': 'pygeoapi.provider.filesystem.FileSystemProvider'
    },
    'formatter': {
        'CSV': 'pygeoapi.formatter.csv_.CSVFormatter'
    },
    'process': {
        'HelloWorld': 'pygeoapi.process.hello_world.HelloWorldProcessor',
        'Reprojector': 'pygeoapi.process.reproject-coords.WKTReprojectorProcessor'
    },
    'process_manager': {
        'TinyDB': 'pygeoapi.process.manager.tinydb_.TinyDBManager'
    }
}


def load_plugin(plugin_type, plugin_def):
    """
    loads plugin by name

    :param plugin_type: type of plugin (provider, formatter)
    :param plugin_def: plugin definition

    :returns: plugin object
    """

    name = plugin_def['name']

    if name == "OGR":
        os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = os.environ.get(
            "OGR_GEOJSON_MAX_OBJ_SIZE", "20MB")

    if plugin_type not in PLUGINS.keys():
        msg = 'Plugin type {} not found'.format(plugin_type)
        LOGGER.exception(msg)
        raise InvalidPluginError(msg)

    plugin_list = PLUGINS[plugin_type]

    LOGGER.debug('Plugins: {}'.format(plugin_list))

    if '.' not in name and name not in plugin_list.keys():
        msg = 'Plugin {} not found'.format(name)
        LOGGER.exception(msg)
        raise InvalidPluginError(msg)

    if '.' in name:  # dotted path
        packagename, classname = name.rsplit('.', 1)
    else:  # core formatter
        packagename, classname = plugin_list[name].rsplit('.', 1)

    LOGGER.debug('package name: {}'.format(packagename))
    LOGGER.debug('class name: {}'.format(classname))

    module = importlib.import_module(packagename)
    class_ = getattr(module, classname)
    plugin = class_(plugin_def)

    # TODO remove conditional after debugging
    if 'TinyDBManager' == classname:
        LOGGER.debug('plugin: {}'.format(plugin))
    return plugin


class InvalidPluginError(Exception):
    """Invalid plugin"""
    pass
