# =================================================================
#
# Authors: Benjamin Webb <bwebb@lincolninst.edu>
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 Benjamin Webb
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

from copy import deepcopy
import json
from urllib.parse import urlparse
from sodapy import Socrata
import logging

from pygeoapi.provider.base import (BaseProvider, ProviderQueryError,
                                    ProviderConnectionError)
from pygeoapi.util import format_datetime, crs_transform

LOGGER = logging.getLogger(__name__)

FIELD_NAME = 'columns_field_name'
DATA_TYPE = 'columns_datatype'


class SODAServiceProvider(BaseProvider):
    """Socrata Open Data API Provider
    """

    def __init__(self, provider_def):
        """
        SODA Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data, id_field, name set in parent class

        :returns: pygeoapi.provider.socrata.SODAServiceProvider
        """
        LOGGER.debug('Logger SODA Init')

        super().__init__(provider_def)
        self.resource_id = provider_def['resource_id']
        self.token = provider_def.get('token')
        self.geom_field = provider_def.get('geom_field')
        self.url = urlparse(self.data).netloc
        self.client = Socrata(self.url, self.token)
        self.get_fields()

    def get_fields(self):
        """
        Get fields of SODA Provider

        :returns: dict of fields
        """

        if not self.fields:

            try:
                [dataset] = self.client.datasets(ids=[self.resource_id])
                resource = dataset['resource']
            except json.decoder.JSONDecodeError as err:
                LOGGER.error(f'Bad response at {self.data}')
                raise ProviderConnectionError(err)

            fields = self.properties or resource[FIELD_NAME]
            for field in fields:
                idx = resource[FIELD_NAME].index(field)
                self.fields[field] = {'type': resource[DATA_TYPE][idx]}

        return self.fields

    @crs_transform
    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None, **kwargs):
        """
        SODA query

        :param offset: starting record to return (default 0)
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

        # Default feature collection and request parameters

        params = {
            'content_type': 'geojson',
            'select': self._make_fields(select_properties),
            'where': self._make_where(bbox, datetime_, properties),
        }

        fc = {
            'type': 'FeatureCollection',
            'features': [],
            'numberMatched': self._get_count(params)
        }

        if resulttype == 'hits':
            # Return hits
            LOGGER.debug('Returning hits')
            return fc

        if sortby != []:
            params['order'] = self._make_orderby(sortby)

        params['offset'] = offset
        params['limit'] = limit

        def make_feature(f):
            f['id'] = f['properties'].pop(self.id_field)
            if skip_geometry:
                f['geometry'] = None
            return f

        try:
            LOGGER.debug('Sending query')
            resp = self.client.get(self.resource_id, **params)

            LOGGER.debug('Making features')
            fc['features'] = [make_feature(f) for f in resp['features']]
        except Exception as err:
            msg = f'Provider query error: {err}'
            LOGGER.error(msg)
            raise ProviderQueryError(msg)

        fc['numberReturned'] = len(resp['features'])

        return fc

    @crs_transform
    def get(self, identifier, **kwargs):
        """
        Query SODA by id

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """
        params = {
            'content_type': 'geojson',
            'limit': 1,
        }
        properties = [(self.id_field, identifier), ]
        params['where'] = self._make_where(properties=properties)

        # Form URL for GET request
        LOGGER.debug('Sending query')
        fc = self.client.get(self.resource_id, **params)
        f = fc.get('features').pop()
        f['id'] = f['properties'].pop(self.id_field)
        return f

    def _make_fields(self, select_properties=[]):
        """
        Make SODA select clause

        :param select_properties: list of property names

        :returns: SODA query `$select` clause
        """
        if self.properties == [] and select_properties == []:
            return '*'

        if self.properties != [] and select_properties != []:
            outFields = set(self.properties) & set(select_properties)
        else:
            outFields = set(self.properties) | set(select_properties)

        outFields = set([self.id_field, *outFields])
        return ','.join(outFields)

    @staticmethod
    def _make_orderby(sortby=[]):
        """
        Make SODA order clause

        :param sortby: `list` of dicts (property, order)

        :returns: SODA query `$order` clause
        """
        __ = {'+': 'ASC', '-': 'DESC'}
        ret = [f"{_['property']} {__[_['order']]}" for _ in sortby]

        return ','.join(ret)

    def _make_where(self, bbox=[], datetime_=None, properties=[]):
        """
        Private function: Make SODA filter from query properties

        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param properties: `list` of tuples (name, value)

        :returns: SODA query `$where` clause
        """

        ret = []

        if properties != []:
            ret.extend(
                [f'{k} = "{v}"' for (k, v) in properties]
            )

        if bbox != []:
            minx, miny, maxx, maxy = bbox
            bpoly = f"'POLYGON (({minx} {miny}, {maxx} {miny}, \
                     {maxx} {maxy}, {minx} {maxy}, {minx} {miny}))'"
            ret.append(f"within_polygon({self.geom_field}, {bpoly})")

        if datetime_ is not None:

            fmt_ = '%Y-%m-%dT%H:%M:%S'
            if '/' in datetime_:
                time_start, time_end = datetime_.split('/')
                if time_start != '..':
                    iso_time = format_datetime(time_start, fmt_)
                    ret.append(f"{self.time_field} >= '{iso_time}'")
                if time_end != '..':
                    iso_time = format_datetime(time_end, fmt_)
                    ret.append(f"{self.time_field} <= '{iso_time}'")

            else:
                iso_time = format_datetime(datetime_, fmt_)
                ret.append(f"{self.time_field} = '{iso_time}'")

        return ' AND '.join(ret)

    def _get_count(self, params):
        """
        Count number of features from query args

        :param params: `dict` of query params

        :returns: `int` of feature count
        """
        params = deepcopy(params)

        params['select'] = 'count(*)'
        params['content_type'] = 'json'

        [response] = self.client.get(self.resource_id, **params)
        return int(response['count'])

    def __repr__(self):
        return f'<SODAServiceProvider> {self.data}'
