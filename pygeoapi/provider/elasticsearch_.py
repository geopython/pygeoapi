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

import logging

from elasticsearch import Elasticsearch, exceptions
from elasticsearch.client.indices import IndicesClient

from pygeoapi.provider.base import (BaseProvider, ProviderConnectionError,
                                    ProviderQueryError)

LOGGER = logging.getLogger(__name__)


class ElasticsearchProvider(BaseProvider):
    """Elasticsearch Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.providers.elasticsearch_.ElasticsearchProvider
        """

        BaseProvider.__init__(self, provider_def)

        url_tokens = self.data.split('/')

        LOGGER.debug('Setting Elasticsearch properties')
        self.es_host = url_tokens[2]
        self.index_name = url_tokens[-2]
        self.type_name = url_tokens[-1]
        LOGGER.debug('host: {}'.format(self.es_host))
        LOGGER.debug('index: {}'.format(self.index_name))
        LOGGER.debug('type: {}'.format(self.type_name))

        LOGGER.debug('Connecting to Elasticsearch')
        self.es = Elasticsearch(self.es_host)
        if not self.es.ping():
            msg = 'Cannot connect to Elasticsearch'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

        LOGGER.debug('Grabbing field information')
        try:
            self.fields = self.get_fields()
        except exceptions.NotFoundError as err:
            LOGGER.error(err)
            raise ProviderQueryError(err)

    def get_fields(self):
        """
         Get provider field information (names, types)

        :returns: dict of fields
        """

        fields_ = {}
        ic = IndicesClient(self.es)
        ii = ic.get(self.index_name)
        p = ii[self.index_name]['mappings'][self.type_name]['properties']['properties']  # noqa

        for k, v in p['properties'].items():
            if v['type'] == 'text':
                type_ = 'string'
            else:
                type_ = v['type']
            fields_[k] = {'type': type_}

        return fields_

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], time=None, properties=[]):
        """
        query Elasticsearch index

        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param time: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)

        :returns: dict of 0..n GeoJSON features
        """

        query = {'query': {'bool': {'filter': []}}}
        filter_ = []

        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }

        if resulttype == 'hits':
            LOGGER.debug('hits only specified')
            limit = 0

        if bbox:
            LOGGER.debug('processing bbox parameter')
            minx, miny, maxx, maxy = bbox
            bbox_filter = {
                'geo_shape': {
                    'geometry': {
                        'shape': {
                            'type': 'envelope',
                            'coordinates': [[minx, miny], [maxx, maxy]]
                        },
                        'relation': 'intersects'
                    }
                }
            }

            query['query']['bool']['filter'].append(bbox_filter)

        if time is not None:
            LOGGER.debug('processing time parameter')
            if self.time_field is None:
                LOGGER.error('time_field not enabled for collection')
                raise ProviderQueryError()

            time_field = 'properties.{}'.format(self.time_field)

            if '/' in time:  # envelope
                LOGGER.debug('detected time range')
                time_begin, time_end = time.split('/')

                range_ = {
                    'range': {
                        time_field: {
                            'gte': time_begin,
                            'lte': time_end,
                        }
                    }
                }

                filter_.append(range_)

            else:  # time instant
                LOGGER.debug('detected time instant')
                filter_.append({'match': {time_field: time}})

            LOGGER.debug(filter_)
            query['query']['bool']['filter'].append(filter_)

        if properties:
            LOGGER.debug('processing properties')
            for prop in properties:
                pf = {
                    'match': {
                        'properties.{}'.format(prop[0]): prop[1]
                    }
                }
                query['query']['bool']['filter'].append(pf)

        try:
            LOGGER.debug('querying Elasticsearch')
            results = self.es.search(index=self.index_name, from_=startindex,
                                     size=limit, body=query)
        except exceptions.ConnectionError as err:
            LOGGER.error(err)
            raise ProviderConnectionError()
        except exceptions.RequestError as err:
            LOGGER.error(err)
            raise ProviderQueryError()
        except exceptions.NotFoundError as err:
            LOGGER.error(err)
            raise ProviderQueryError()

        feature_collection['numberMatched'] = results['hits']['total']

        if resulttype == 'hits':
            return feature_collection

        feature_collection['numberReturned'] = len(results['hits']['hits'])

        LOGGER.debug('serializing features')
        for feature in results['hits']['hits']:
            id_ = feature['_source']['properties'][self.id_field]
            LOGGER.debug('serializing id {}'.format(id_))
            feature['_source']['ID'] = id_
            feature_collection['features'].append(feature['_source'])

        return feature_collection

    def get(self, identifier):
        """
        Get ES document by id

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """

        try:
            LOGGER.debug('Fetching identifier {}'.format(identifier))
            result = self.es.get(self.index_name, doc_type=self.type_name,
                                 id=identifier)
            LOGGER.debug('Serializing feature')
            id_ = result['_source']['properties'][self.id_field]
            result['_source']['ID'] = id_
        except Exception as err:
            LOGGER.error(err)
            return None

        return result['_source']

    def __repr__(self):
        return '<ElasticsearchProvider> {}'.format(self.data)
