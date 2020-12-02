# =================================================================
#
# Authors: Luís Moreira de Sousa <luis.de.sousa@protonmail.com>
#
# Copyright (c) 2020 Luís Moreira de Sousa
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
from SPARQLWrapper import SPARQLWrapper, JSON, RDFXML
from rdflib import Graph, plugin
from rdflib.serializer import Serializer
import json
import shapely.wkt
import geojson

from base import (BaseProvider, ProviderQueryError,
                                    ProviderItemNotFoundError)

#LOGGER = logging.getLogger(__name__)

class GeoSPARSQLProvider(BaseProvider):
    """Generic provider for GeoSPARQL endpoints 
    based on RDFlib and SPARQLWrapper
    """

    def __init__(self, provider_def):
        """
        GeoSPARSQLProvider Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class
                             data contains the connection information
                             for class DatabaseCursor

        :returns: pygeoapi.provider.base.GeoSPARSQLProvider
        """

        BaseProvider.__init__(self, provider_def)

        self.endpoint = provider_def['data']
        self.id_prefix = provider_def['id_prefix']
        
 #       LOGGER.debug('Setting GeoSPARQL properties:')
 #       LOGGER.debug('Endpoint:{}'.format(self.endpoint)
 #       LOGGER.debug('Identifier prefix:{}'.format(self.id_prefix)


    def query(self):
        """
        query the provider

        :returns: dict of 0..n GeoJSON features or coverage data
        """

 
    def _issueQuery(self, query, retFormat):
        
        sparql = SPARQLWrapper(self.endpoint)
        sparql.setQuery(query)
        sparql.setReturnFormat(retFormat)
        
        try:
            results = sparql.query().convert()
        except Exception as err:
            LOGGER.error('Error issuing sqarql query: {}'.format(query))
            LOGGER.error(err)
            raise ProviderQueryError(err)

        return results

    
    def get(self, identifier):
        """
        query the provider by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """

#        print("The endpoint: " + str(self.endpoint))
        sparql = SPARQLWrapper(self.endpoint)
#
#        # Obtain Feature properties
#        sparql.setQuery("""
#           CONSTRUCT {<%s> ?predicate ?object}
#               WHERE {<%s> ?predicate ?object}
#        """ % (identifier, identifier))
#
#        sparql.setReturnFormat(RDFXML)
#        results = sparql.query().convert()
       
        # Obtain Feature properties 
        results = self._issueQuery("""
            CONSTRUCT {<%s> ?predicate ?object}
                WHERE {<%s> ?predicate ?object}
        """ % (identifier, identifier), RDFXML)
       
        props = json.loads(results.serialize(format='json-ld', indent=2))

        # Obtain Feature geometry
        resultsGeo = self._issueQuery("""
             PREFIX geo: <http://www.opengis.net/ont/geosparql#>
             SELECT ?predicate ?object 
              WHERE { <%s> geo:hasGeometry ?geom .
                      ?geom ?predicate ?object . }
        """ % (identifier), JSON)

        predicate = resultsGeo["results"]["bindings"][1]["predicate"] 
        object = resultsGeo["results"]["bindings"][1]["object"] 

        if predicate["value"] == "http://www.opengis.net/ont/geosparql#asWKT":
            geom = shapely.wkt.loads(object["value"])
        else:
            raise ProviderNoDataError("Geometry not found for feature %s"
                                      % (identifier))


        return geojson.Feature(geometry=geom, properties=props)

        # This is a string, must be converted into a dictionary
        # return results.serialize(format='json-ld', indent=2)

        # Convert WKT to GeoJSON
        # https://gist.github.com/drmalex07/5a54fc4f1db06a66679e


    def create(self, new_feature):
        """Create a new feature
        """


    def update(self, identifier, new_feature):
        """Updates an existing feature id with new_feature

        :param identifier: feature id
        :param new_feature: new GeoJSON feature dictionary
        """


    def delete(self, identifier):
        """Deletes an existing feature

        :param identifier: feature id
        """


