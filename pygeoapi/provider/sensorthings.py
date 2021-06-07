# =================================================================
#
# Authors: Jorge Samuel Mendes de Jesus <jorge.dejesus@protonmail.net>
#          Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2018 Jorge Samuel Mendes de Jesus
# Copyright (c) 2021 Tom Kralidis
# Copyright (c) 2020 Francesco Bartoli
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

import requests
import logging
from pygeoapi.provider.base import (BaseProvider, ProviderQueryError,
                                    ProviderConnectionError,
                                    ProviderItemNotFoundError)

LOGGER = logging.getLogger(__name__)
LOGGER.debug("Logger Init")

EXPAND = {
    'Things': 'Locations,Datastreams',
    'Datastreams': 'Sensor,ObservedProperty,Thing,\
        Observations($orderby=phenomenonTime desc)',
    'Observations': 'Datastream,FeatureOfInterest'
}


class SensorthingsProvider(BaseProvider):
    """Sensorthings API Provider
    """

    def __init__(self, provider_def):
        """
        Sensorthings Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class

        :returns: pygeoapi.provider.base.SensorthingsProvider
        """
        LOGGER.debug("Logger STA Init")
        super().__init__(provider_def)
        self.entity = provider_def.get('entity')
        self.rel_link = provider_def.get('rel_link')

    def _load(self, startindex=0, limit=10, resulttype='results',
              identifier=None, bbox=[], datetime_=None, properties=[],
              select_properties=[], skip_geometry=False, q=None):
        """
        Load sensorthings data
        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)
        :param q: full-text search term(s)
        :returns: dict of GeoJSON FeatureCollection
        """

        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }

        params = {
         '$expand': EXPAND[self.entity], '$skip': startindex, '$top': limit
         }

        # Form URL for GET request
        url = self.data + self.entity
        if identifier:
            r = requests.get(url + f'({identifier})', params=params)
            v = [r.json(), ]
        else:
            r = requests.get(url, params=params)
            v = r.json().get('value')

        if r.status_code == requests.codes.bad:
            LOGGER.error('Bad http response code')
            raise ProviderConnectionError('Bad http response code')

        # if hits, return count
        if resulttype == 'hits':
            LOGGER.debug('Returning hits')
            feature_collection['numberMatched'] = len(v)
            return feature_collection

        for entity in v:
            # Make feature
            f = {
                'type': 'Feature', 'properties': {},
                'geometry': None,
                'id': str(entity.pop(self.id_field))
                }

            # Make geometry
            if not skip_geometry:
                try:
                    if self.entity == 'Things':
                        f['geometry'] = entity \
                            .pop('Locations')[0]['location']
                    elif self.entity == 'Datastreams':
                        f['geometry'] = entity.pop('observedArea')
                    elif self.entity == 'Observations':
                        f['geometry'] = entity \
                            .get('FeatureOfInterest').pop('feature')
                except ProviderItemNotFoundError as err:
                    LOGGER.error(err)
                    raise ProviderItemNotFoundError(err)

            # Fill properties block
            if self.properties or select_properties:
                keys = set(self.properties) | set(select_properties)
            else:
                keys = ()
            f['properties'] = self._parse_properties(entity, keys)

            feature_collection['features'].append(f)

        if identifier:
            return f
        else:
            return feature_collection

    def _parse_properties(self, entity, keys=()):
        """
        Private function: parse sensorthings entity into feature property
        :param entity: sensorthings entity
        :param keys: keys used in properties block
        :returns: dict of sensorthings feature properties
        """
        for k, v in entity.items():
            # Clean @iot.selflink for html
            if isinstance(v, dict) and v.get('@iot.selfLink'):
                v['@iot.selfLink'] += '?'
            elif isinstance(v, list) and v[0].get('@iot.selfLink'):
                v[0]['@iot.selfLink'] += '?'
            elif k == '@iot.selfLink':
                entity[k] += '?'

            # Create relative links
            if k in ['Thing', 'Datastream']:
                entity[k] = '{}/collections/{}/items/{}'.format(
                    self.rel_link, k + 's', v['@iot.id']
                )
            elif k in ['Datastreams', 'Observations']:
                for i, _ in enumerate(v):
                    v[i] = '{}/collections/{}/items/{}'.format(
                        self.rel_link, k, _['@iot.id']
                    )

        if keys:
            ret = {}
            for k in keys:
                # Make properties block
                try:
                    ret[k] = entity.pop(k)
                except KeyError as err:
                    LOGGER.error(err)
                    raise ProviderQueryError(err)

            return ret

        return entity

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None):
        """
        Sensorthings query
        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)
        :param q: full-text search term(s)
        :returns: dict of GeoJSON FeatureCollection
        """

        return self._load(startindex, limit, resulttype,
                          select_properties=select_properties,
                          skip_geometry=skip_geometry)

    def get(self, identifier):
        """
        query the provider by id
        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """
        return self._load(identifier=identifier)

    def __repr__(self):
        return '<SensorthingsProvider> {}, {}'.format(self.data, self.table)
