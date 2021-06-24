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

from requests import get, codes
from requests.compat import urljoin
import logging
from pygeoapi.provider.base import (BaseProvider, ProviderQueryError,
                                    ProviderConnectionError,
                                    ProviderItemNotFoundError)
from pygeoapi.util import yaml_load
import os

LOGGER = logging.getLogger(__name__)

_EXPAND = {
    'Things': """
        Locations,
        Datastreams(
            $select=@iot.id,properties
            )
    """,
    'Observations': """
        Datastream(
            $select=@iot.id,properties
            ),
        FeatureOfInterest
    """,
    'Datastreams': """
        Sensor
        ,ObservedProperty
        ,Thing(
            $select=@iot.id,properties
            )
        ,Thing/Locations(
            $select=location
            )
        ,Observations(
            $select=@iot.id;
            $orderby=phenomenonTime_desc
            )
        ,Observations/FeatureOfInterest(
            $select=feature
            )
    """
}
EXPAND = {k: ''.join(v.split()).replace('_', ' ')
          for (k, v) in _EXPAND.items()}


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
        self.intralink = provider_def.get('intralink', False)
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
        if properties or bbox or datetime_:
            params['$filter'] = self._make_filter(properties, bbox, datetime_)
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

        return self._load(startindex, limit, resulttype, bbox=bbox,
                          datetime_=datetime_, properties=properties,
                          sortby=sortby, select_properties=select_properties,
                          skip_geometry=skip_geometry)

    def get(self, identifier, **kwargs):
        """
        Query the STA by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """
        return self._load(identifier=identifier)

    def _make_filter(self, properties, bbox=[], datetime_=None):
        """
        Make STA filter from query properties

        :param properties: list of tuples (name, value)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)

        :returns: STA $filter string of properties
        """
        ret = []
        for (name, value) in properties:
            if name in EXPAND[self.entity]:
                ret.append(f'{name}/@iot.id eq {value}')
            else:
                ret.append(f'{name} eq {value}')

        if bbox:
            minx, miny, maxx, maxy = bbox
            bbox_ = f'POLYGON (({minx} {miny}, {maxx} {miny}, \
                     {maxx} {maxy}, {minx} {maxy}, {minx} {miny}))'
            if self.entity == 'Things':
                loc = 'Locations/location'
            elif self.entity == 'Datastreams':
                loc = 'Thing/Locations/location'
            elif self.entity == 'Observations':
                loc = 'FeatureOfInterest/feature'
            ret.append(f"st_within({loc}, geography'{bbox_}')")

        if datetime_ is not None:
            if self.time_field is None:
                LOGGER.error('time_field not enabled for collection')
                raise ProviderQueryError()

            if '/' in datetime_:
                time_start, time_end = datetime_.split('/')
                ret.append(f'{self.time_field} ge {time_start}')
                ret.append(f'{self.time_field} le {time_end}')
            else:
                ret.append(f'{self.time_field} eq {datetime_}')

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
            if (self.id_field == '@iot.id'
                    and _['property'] in EXPAND[self.entity]):
                ret.append(f"{_['property']}/@iot.id {_map[_['order']]}")
            else:
                ret.append(f"{_['property']} {_map[_['order']]}")
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
                return entity['Thing'].pop('Locations')[
                    0]['location']
            elif self.entity == 'Observations':
                return entity.get('FeatureOfInterest').pop('feature')
        except ProviderItemNotFoundError as err:
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)

    def _expand_properties(self, entity, keys=(), uri=''):
        """
        Private function: Parse STA entity into feature

        :param entity: sensorthings entity
        :param keys: keys used in properties block
        :param uri: uri of STA entity

        :returns: dict of sensorthings feature properties
        """
        for k, v in entity.items():
            # Create intra links
            path_ = 'collections/{}/items/{}'

            if self.uri_field is not None and k in ['properties']:
                uri = v.get(self.uri_field, '')

            elif self.intralink and k in ['Thing', 'Datastream']:
                if self.uri_field is not None:
                    entity[k] = v['properties'][self.uri_field]
                elif self.id_field == '@iot.id':
                    entity[k] = urljoin(
                        self.rel_link,
                        path_.format(k + 's', v['@iot.id'])
                    )

            elif self.intralink and k in ['Datastreams', 'Observations']:
                if self.uri_field is not None and k not in ['Observations']:
                    for i, _v in enumerate(v):
                        v[i] = _v['properties'][self.uri_field]
                elif self.id_field == '@iot.id':
                    for i, _v in enumerate(v):
                        v[i] = urljoin(
                            self.rel_link,
                            path_.format(k, _v['@iot.id'])
                        )

        # Make properties block
        if keys:
            ret = {}
            for k in keys:
                try:
                    ret[k] = entity.pop(k)
                except KeyError as err:
                    LOGGER.error(err)
                    raise ProviderQueryError(err)
            entity = ret

        # Retain URI if present
        if self.uri_field is not None and uri != '':
            entity[self.uri_field] = uri

        return entity

    def __repr__(self):
        return '<SensorthingsProvider> {}, {}'.format(self.data, self.entity)
