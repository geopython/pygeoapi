# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2026 Tom Kralidis
# Copyright (c) 2026 Francesco Bartoli
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
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger(__name__)


@dataclass
class PluginContext:
    """
    Inject dependencies with a context object into plugins.

    This allows passing runtime dependencies to plugins without
    relying on global state or complex config dictionaries.

    Attributes:
        config: Original plugin configuration dictionary
        logger: Optional injected logger instance
        locales: Optional list of supported locale codes
        base_url: Optional API base URL for link generation

    Example:
        >>> from pygeoapi.plugin import PluginContext, load_plugin
        >>> context = PluginContext(
        ...     config={'name': 'GeoJSON', 'type': 'feature',
        ...             'data': 'obs.geojson'},
        ...     logger=custom_logger,
        ...     base_url='https://api.example.com'
        ... )
        >>> provider = load_plugin('provider', context.config, context=context)
    """

    config: Dict[str, Any]
    logger: Optional[Any] = None
    locales: Optional[List[str]] = None
    base_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to plain dict format for backwards compatibility.

        :returns: Dictionary with config and injected dependencies
        """
        result = dict(self.config)
        if self.logger:
            result["_logger"] = self.logger
        if self.base_url:
            result["_base_url"] = self.base_url
        if self.locales:
            result["_locales"] = self.locales
        return result


#: Loads provider plugins to be used by pygeoapi,\
#: formatters and processes available
PLUGINS = {
    'provider': {
        'AzureBlobStorage': 'pygeoapi.provider.azure_.AzureBlobStorageProvider',  # noqa
        'CSV': 'pygeoapi.provider.csv_.CSVProvider',
        'CSWFacade': 'pygeoapi.provider.csw_facade.CSWFacadeProvider',
        'Elasticsearch': 'pygeoapi.provider.elasticsearch_.ElasticsearchProvider',  # noqa
        'ElasticsearchCatalogue': 'pygeoapi.provider.elasticsearch_.ElasticsearchCatalogueProvider',  # noqa
        'ERDDAPTabledap': 'pygeoapi.provider.erddap.TabledapProvider',
        'ESRI': 'pygeoapi.provider.esri.ESRIServiceProvider',
        'FileSystem': 'pygeoapi.provider.filesystem.FileSystemProvider',
        'GeoJSON': 'pygeoapi.provider.geojson.GeoJSONProvider',
        'Hateoas': 'pygeoapi.provider.hateoas.HateoasProvider',
        'MapScript': 'pygeoapi.provider.mapscript_.MapScriptProvider',
        'MongoDB': 'pygeoapi.provider.mongo.MongoProvider',
        'MVT-tippecanoe': 'pygeoapi.provider.mvt_tippecanoe.MVTTippecanoeProvider',  # noqa: E501
        'MVT-elastic': 'pygeoapi.provider.mvt_elastic.MVTElasticProvider',
        'MVT-proxy': 'pygeoapi.provider.mvt_proxy.MVTProxyProvider',
        'MySQL': 'pygeoapi.provider.sql.MySQLProvider',
        'MVT-postgresql': 'pygeoapi.provider.mvt_postgresql.MVTPostgreSQLProvider',  # noqa: E501
        'OracleDB': 'pygeoapi.provider.oracle.OracleProvider',
        'OGR': 'pygeoapi.provider.ogr.OGRProvider',
        'OpenSearch': 'pygeoapi.provider.opensearch_.OpenSearchProvider',
        'Parquet': 'pygeoapi.provider.parquet.ParquetProvider',
        'PostgreSQL': 'pygeoapi.provider.sql.PostgreSQLProvider',
        'rasterio': 'pygeoapi.provider.rasterio_.RasterioProvider',
        'SensorThings': 'pygeoapi.provider.sensorthings.SensorThingsProvider',
        'SensorThingsEDR': 'pygeoapi.provider.sensorthings_edr.SensorThingsEDRProvider',  # noqa: E501
        'SQLiteGPKG': 'pygeoapi.provider.sqlite.SQLiteGPKGProvider',
        'Socrata': 'pygeoapi.provider.socrata.SODAServiceProvider',
        'TinyDB': 'pygeoapi.provider.tinydb_.TinyDBProvider',
        'TinyDBCatalogue': 'pygeoapi.provider.tinydb_.TinyDBCatalogueProvider',
        'WMSFacade': 'pygeoapi.provider.wms_facade.WMSFacadeProvider',
        'WMTSFacade': 'pygeoapi.provider.wmts_facade.WMTSFacadeProvider',
        'xarray': 'pygeoapi.provider.xarray_.XarrayProvider',
        'xarray-edr': 'pygeoapi.provider.xarray_edr.XarrayEDRProvider'
    },
    'formatter': {
        'CSV': 'pygeoapi.formatter.csv_.CSVFormatter'
    },
    'process': {
        'HelloWorld': 'pygeoapi.process.hello_world.HelloWorldProcessor',
        'ShapelyFunctions': 'pygeoapi.process.shapely_functions.ShapelyFunctionsProcessor',  # noqa: E501
        'Echo': 'pygeoapi.process.echo.EchoProcessor'
    },
    'process_manager': {
        'Dummy': 'pygeoapi.process.manager.dummy.DummyManager',
        'MongoDB': 'pygeoapi.process.manager.mongodb_.MongoDBManager',
        'TinyDB': 'pygeoapi.process.manager.tinydb_.TinyDBManager',
        'PostgreSQL': 'pygeoapi.process.manager.postgresql.PostgreSQLManager'
    },
    'pubsub': {
        'HTTP': 'pygeoapi.pubsub.http.HTTPPubSubClient',
        'Kafka': 'pygeoapi.pubsub.kafka.KafkaPubSubClient',
        'MQTT': 'pygeoapi.pubsub.mqtt.MQTTPubSubClient'
    }
}


def load_plugin(
    plugin_type: str, plugin_def: dict, context: Optional[PluginContext] = None
) -> Any:
    """
    Loads plugin by name with optional dependency injection.

    :param plugin_type: type of plugin (provider, formatter, process, etc.)
    :param plugin_def: plugin definition dictionary
    :param context: optional context with injected dependencies

    :returns: plugin object

    Example:
        # Plain mode (backwards compatible)
        >>> provider = load_plugin('provider', {
        ...     'name': 'GeoJSON',
        ...     'type': 'feature',
        ...     'data': 'obs.geojson'
        ... })

        # Modern mode with dependencies
        >>> context = PluginContext(
        ...     config={'name': 'GeoJSON', 'type': 'feature',
        ...             'data': 'obs.geojson'},
        ...     logger=custom_logger
        ... )
        >>> provider = load_plugin('provider', context.config, context=context)
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

    # Support injected dependencies via PluginContext
    if context is not None:
        # Try context-aware constructor first
        try:
            plugin = class_(plugin_def, context=context)
            LOGGER.debug(f"{name} initialized with PluginContext")
        except TypeError as err:
            # Fallback: legacy constructor without context parameter
            LOGGER.debug(
                f"{name} does not support PluginContext, "
                f"using legacy init: {err}"
            )
            plugin = class_(plugin_def)
    else:
        # Plain mode: no more context provided
        plugin = class_(plugin_def)

    return plugin


class InvalidPluginError(Exception):
    """Invalid plugin"""
    pass
