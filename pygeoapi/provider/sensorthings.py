# =================================================================
#
# Authors: Benjamin Webb <benjamin.miller.webb@gmail.com>
#
# Copyright (c) 2021 Benjamin Webb
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

from requests import get
from requests import codes
from requests.compat import urljoin
import logging
from pygeoapi.provider.base import (BaseProvider, ProviderQueryError,
                                    ProviderConnectionError,
                                    ProviderItemNotFoundError)
from pygeoapi.util import yaml_load
import os

LOGGER = logging.getLogger(__name__)

EXPAND = {
    'Things': 'Locations,Datastreams($select=@iot.id)',
    'Observations': 'Datastream($select=@iot.id),FeatureOfInterest',
    'Datastreams': 'Sensor,ObservedProperty,Thing($select=@iot.id),\
     Observations($select=@iot.id;$expand=FeatureOfInterest($select=feature);\
      $orderby=phenomenonTime desc)'
}


class SensorthingsProvider(BaseProvider):
    """Sensorthings API (STA) Provider
    """

    def __init__(self, provider_def):
        """
        STA Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class

        :returns: pygeoapi.provider.base.SensorthingsProvider
        """
        LOGGER.debug("Logger STA Init")

        super().__init__(provider_def)
        self.entity = provider_def.get('entity')
        self.url = self.data + self.entity
        if self.id_field is None:
            self.id_field = '@iot.id'

        with open(os.environ.get('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
            CONFIG = yaml_load(fh)
        self.rel_link = CONFIG['server']['url']

        self.get_fields()

    def get_fields(self):
        """
         Get fields of STA Provider

        :returns: dict of fields
        """
        if not self.fields:
            p = {'$expand': EXPAND[self.entity], '$top': 1}
            r = get(self.url, params=p)
            results = r.json()['value'][0]

            for (n, v) in results.items():

                if isinstance(v, (int, float)) or \
                   (isinstance(v, (dict, list)) and n in EXPAND[self.entity]):
                    self.fields[n] = {'type': 'number'}
                elif isinstance(v, str):
                    self.fields[n] = {'type': 'string'}

        return self.fields

    def _load(self, startindex=0, limit=10, resulttype='results',
              identifier=None, bbox=[], datetime_=None, properties=[],
              sortby=[], select_properties=[], skip_geometry=False, q=None):
        """
        Load STA data

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
        # Make params
        params = {
            '$expand': EXPAND[self.entity], '$skip': startindex, '$top': limit
        }
        if properties:
            params['$filter'] = self._make_filter(properties)
        if sortby:
            params['$orderby'] = self._make_orderby(sortby)

        # Form URL for GET request
        if identifier:
            r = get(f'{self.url}({identifier})', params=params)
            v = [r.json(), ]
        else:
            r = get(self.url, params=params)
            v = r.json().get('value')

        if r.status_code == codes.bad:
            LOGGER.error('Bad http response code')
            raise ProviderConnectionError('Bad http response code')

        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }

        # if hits, return count
        if resulttype == 'hits':
            LOGGER.debug('Returning hits')
            feature_collection['numberMatched'] = len(v)
            return feature_collection

        keys = () if not self.properties and not select_properties else \
            set(self.properties) | set(select_properties)

        for entity in v:
            # Make feature
            f = {
                'type': 'Feature', 'properties': {},
                'geometry': None, 'id': str(entity.pop(self.id_field))
            }

            # Make geometry
            if not skip_geometry:
                f['geometry'] = self._geometry(entity)

            # Fill properties block
            f['properties'] = self._expand_properties(entity, keys)

            feature_collection['features'].append(f)

        if identifier:
            return f
        else:
            return feature_collection

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None, **kwargs):
        """
        STA query

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

        return self._load(startindex, limit, resulttype, properties=properties,
                          sortby=sortby, select_properties=select_properties,
                          skip_geometry=skip_geometry)

    def get(self, identifier, **kwargs):
        """
        Query the STA by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """
        return self._load(identifier=identifier)

    def _make_filter(self, properties):
        """
        Make STA filter from query properties

        :param properties: list of tuples (name, value)

        :returns: STA $filter string of properties
        """
        ret = []
        for (name, value) in properties:
            if name in EXPAND[self.entity]:
                ret.append(f'{name}/@iot.id eq {value}')
            else:
                ret.append(f'{name} eq {value}')

        return ' and '.join(ret)

    def _make_orderby(self, sortby):
        """
        Make STA filter from query properties

        :param sortby: list of dicts (property, order)

        :returns: STA $orderby string
        """
        ret = []
        _map = {'+': 'asc', '-': 'desc'}
        for _ in sortby:
            if _['property'] in EXPAND[self.entity]:
                ret.append(f'{_["property"]}/@iot.id {_map[_["order"]]}')
            else:
                ret.append(f'{property} {_map[_["order"]]}')
        return ','.join(ret)

    def _geometry(self, entity):
        """
        Private function: Retrieve STA geometry

        :param entity: sensorthings entity

        :returns: GeoJSON Geometry for feature
        """
        try:
            if self.entity == 'Things':
                return entity.pop('Locations')[0]['location']
            elif self.entity == 'Datastreams':
                return entity['Observations'][0][
                    'FeatureOfInterest'].pop('feature')
            elif self.entity == 'Observations':
                return entity.get('FeatureOfInterest').pop('feature')
        except ProviderItemNotFoundError as err:
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)

    def _expand_properties(self, entity, keys=()):
        """
        Private function: Parse STA entity into feature

        :param entity: sensorthings entity
        :param keys: keys used in properties block

        :returns: dict of sensorthings feature properties
        """
        for k, v in entity.items():
            # Create relative links
            if k in ['Thing', 'Datastream']:
                _ = 'collections/{}/items/{}'.format(
                    k + 's', v['@iot.id']
                )
                entity[k] = urljoin(self.rel_link, _)
            elif k in ['Datastreams', 'Observations']:
                for i, _v in enumerate(v):
                    _ = 'collections/{}/items/{}'.format(
                        k, _v['@iot.id']
                    )
                    v[i] = urljoin(self.rel_link, _)

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

    def __repr__(self):
        return '<SensorthingsProvider> {}, {}'.format(self.data, self.entity)
