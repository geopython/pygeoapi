# =================================================================
#
# Authors: Jorge Samuel Mendes de Jesus <jorge.dejesus@geocat.net>
#
# Copyright (c) 2018 Jorge Samuel Mendes de Jesus
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

import sqlite3
import logging
import os
import json
from pygeoapi.provider.base import BaseProvider, ProviderConnectionError
from pygeoapi.provider import InvalidProviderError

LOGGER = logging.getLogger(__name__)


class GeoPackageProvider(BaseProvider):
    """Generic provider for geopackage based on spatialite and geopackage module
    This module requires install of libsqlite3-mod-spatialite
    TODO: DELETE, UPDATE, CREATE
    """

    def __init__(self, provider_def):
        """
        GeoPackageProvider Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class

        :returns: pygeoapi.providers.base.GeoPackageProvider
        """

        BaseProvider.__init__(self, provider_def)

        self.table = provider_def['table']
        self.view = "vgpkg_" + provider_def['table']

        self.dataDB = None

        LOGGER.debug('Setting GPKG properties:')
        LOGGER.debug('Data source:{}'.format(self.data))
        LOGGER.debug('Name:{}'.format(self.name))
        LOGGER.debug('ID_field:{}'.format(self.id_field))
        LOGGER.debug('Table:{}'.format(self.table))

        self.cursor = self.__load()
        LOGGER.debug('Got cursor from GeoPackage')

    def __response_feature_collection(self):
        """Assembles GeoJSON output from DB query

        :returns: GeoJSON FeaturesCollection
        """

        feature_list = list()
        for row_data in self.dataDB:
            row_data = dict(row_data)  # sqlite3.Row is doesnt support pop
            feature = {
                'type': 'Feature'
            }
            feature["geometry"] = json.loads(
                row_data.pop('AsGeoJSON(geom)')
                )
            feature['properties'] = row_data
            feature['id'] = feature['properties'].pop(self.id_field)
            feature_list.append(feature)

        feature_collection = {
            'type': 'FeatureCollection',
            'features': feature_list
        }

        return feature_collection

    def __response_feature_hits(self, hits):
        """Assembles GeoJSON/Feature number
        e,g: http://localhost:5000/poi/items?
        limit=1&resulttype=hits

        :returns: GeoJSON FeaturesCollection
        """

        feature_collection = {"features": [],
                              "type": "FeatureCollection"}
        feature_collection['numberMatched'] = hits

        return feature_collection

    def __load(self):
        """
        Private method for loading Geopackage,

        :returns: sqlite3.Cursor
        """

        if (os.path.exists(self.data)):
            conn = sqlite3.connect(self.data)
        else:
            raise InvalidProviderError

        try:
            conn.enable_load_extension(True)
        except AttributeError as err:
            LOGGER.error('Extension loading not enabled: {}'.format(err))
            raise ProviderConnectionError()

        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT load_extension('mod_spatialite.so')")
        except sqlite3.OperationalError as err:
            LOGGER.error('Extension loading error: {}'.format(err))
            raise ProviderConnectionError()

        try:
            # Starting GeoPackage support
            cursor.execute("SELECT AutoGPKGStart()")
            result = cursor.fetchall()
            if result[0][0] == 1:
                LOGGER.info("Loaded Geopackage support")
            else:
                LOGGER.info("SELECT AutoGPKGStart() returned 0." +
                            "Likely that this is not a GeoPackage")
                raise InvalidProviderError
        except InvalidProviderError:
            raise

        cursor.execute("PRAGMA table_info({})".format(self.view))
        result = cursor.fetchall()
        try:
            # TODO: Better exceptions declaring
            # InvalidProviderError as Parent class
            assert len(result), "Table not found"
            assert len([item for item in result
                        if self.id_field in item]), "id_field not present"
            assert len([item for item in result
                        if self.id_field in item]), "id_field not present"
            assert len([item for item in result
                        if 'geom' in item]), "geom column not found"

        except InvalidProviderError:
            raise

        self.columns = [item[1] for item in result if item[1] != 'geom']
        self.columns = ",".join(self.columns)+",AsGeoJSON(geom)"

        # Assembling the view
        cursor.execute('CREATE VIRTUAL TABLE IF NOT exists \
            "{}" USING VirtualGPKG("{}")'.format(self.view, self.table))

        return cursor

    def __unload(self):
        """
        Private method for unloading and deleting views in Geopackage,
        this method is only called when provider is delete at end of query

        :returns: None
        """
        self.cursor.execute("DROP TABLE IF EXISTS {}".format(self.view))
        self.cursor.execute("SELECT AutoGPKGStop()")

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], time=None, properties=[]):
        """
        Query Geopackage for all the content.
        e,g: http://localhost:5000/collections/poi/items?
        limit=1&resulttype=results

        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param time: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)

        :returns: GeoJSON FeaturesCollection
        """
        LOGGER.debug('Querying GeoPackage')

        if resulttype == 'hits':
            # Geopackage from gdal has already a feature_count but this is
            # not part of standard
            # gpkg_ogr_contents --> table_name and feature_count
            res = self.cursor.execute("select count(*) as hits from {};"
                                      .format(self.view))

            hits = res.fetchone()["hits"]
            return self.__response_feature_hits(hits)

        end_index = startindex + limit
        # Not working
        # http://localhost:5000/collections/countries/items/?startindex=10
        sql_query = "select {} from {} where rowid >= ? \
        and rowid <= ?;".format(self.columns, self.view)

        LOGGER.debug('SQL Query:{}'.format(sql_query))
        LOGGER.debug('Start Index:{}'.format(startindex))
        LOGGER.debug('End Index'.format(end_index))

        self.dataDB = self.cursor.execute(sql_query, (startindex, end_index, ))

        feature_collection = self.__response_feature_collection()
        return feature_collection

    def get(self, identifier):
        """
        Query the provider for a specific
        feature id e.g: /collections/poi/items/1

        :param identifier: feature id

        :returns: GeoJSON FeaturesCollection
        """

        LOGGER.debug('Get item from Geopackage')

        sql_query = "select {} from {} where {}==?;".format(self.columns,
                                                            self.view,
                                                            self.id_field)

        LOGGER.debug('SQL Query:{}'.format(sql_query))
        LOGGER.debug('Identifier:{}'.format(identifier))

        self.dataDB = self.cursor.execute(sql_query, (identifier, ))

        feature_collection = self.__response_feature_collection()
        return feature_collection

    def __repr__(self):
        return '<GeoPackageProvider> {},{}'.format(self.data, self.table)

    def __del__(self):
        self.__unload()
