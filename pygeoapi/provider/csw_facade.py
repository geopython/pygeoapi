# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2023 Tom Kralidis
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
from urllib.parse import urlencode

from owslib import fes
from owslib.csw import CatalogueServiceWeb
from owslib.ows import ExceptionReport

from pygeoapi.provider.base import (BaseProvider, ProviderConnectionError,
                                    ProviderInvalidQueryError,
                                    ProviderItemNotFoundError,
                                    ProviderQueryError)
from pygeoapi.util import bbox2geojsongeometry, crs_transform, get_typed_value

LOGGER = logging.getLogger(__name__)


class CSWFacadeProvider(BaseProvider):
    """CSW Facade provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.csv_.CSWFacadeProvider
        """

        super().__init__(provider_def)

        self.record_mappings = {
            'type': ('dc:type', 'type'),
            'title': ('dc:title', 'title'),
            'description': ('dct:abstract', 'abstract'),
            'keywords': ('dc:subject', 'subjects'),
            'date': ('dc:date', 'date'),
            'created': ('dct:created', 'created'),
            'updated': ('dct:modified', 'modified'),
            'rights': ('dc:rights', 'rights'),
            'language': ('dc:language', 'language')
        }

        self.fields = self.get_fields()

    def get_fields(self):
        """
         Get provider field information (names, types)

        :returns: dict of fields
        """

        fields = {}
        date_fields = ['date', 'created', 'updated']

        for key in self.record_mappings.keys():
            LOGGER.debug(f'key: {key}')
            fields[key] = {'type': 'string'}

            if key in date_fields:
                fields[key]['format'] = 'date-time'

        return fields

    @crs_transform
    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None, **kwargs):
        """
        CSW GetRecords query

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

        :returns: `dict` of GeoJSON FeatureCollection
        """

        constraints = []

        response = {
            'type': 'FeatureCollection',
            'features': []
        }

        LOGGER.debug('Processing query parameters')

        if bbox:
            LOGGER.debug('Processing bbox parameter')
            LOGGER.debug('Swapping coordinate axis order from xy to yx')
            bbox2 = [bbox[1], bbox[0], bbox[3], bbox[2]]
            constraints.append(fes.BBox(bbox2))

        if datetime_:
            date_property = self.record_mappings[self.time_field][0]
            LOGGER.debug('Processing datetime parameter')
            if '/' in datetime_:
                begin, end = datetime_.split('/')
                LOGGER.debug('Processing time extent')
                constraints.append(fes.PropertyIsGreaterThan(date_property, begin))  # noqa
                constraints.append(fes.PropertyIsLessThan(date_property, end))
            else:
                LOGGER.debug('Processing time instant')
                constraints.append(fes.PropertyIsEqualTo(date_property,
                                                         datetime_))

        for p in properties:
            LOGGER.debug(f'Processing property {p} parameter')
            if p[0] not in list(self.record_mappings.keys()):
                msg = f'Invalid property: {p[0]}'
                LOGGER.error(msg)
                raise ProviderInvalidQueryError(user_msg=msg)

            prop = self.record_mappings[p[0]][0]
            constraints.append(fes.PropertyIsEqualTo(prop, p[1]))

        if q is not None:
            LOGGER.debug('Processing q parameter')
            anytext = fes.PropertyIsLike(propertyname='csw:AnyText', literal=q,
                                         escapeChar='\\', singleChar='?',
                                         wildCard='*')
            constraints.append(anytext)

        if sortby:
            LOGGER.debug('Processing sortby parameter')
            sorts = []
            sort_orders = {
                '+': 'ASC',
                '-': 'DESC'
            }
            for s in sortby:
                sorts.append(fes.SortProperty(
                    self.record_mappings[s['property']][0],
                    sort_orders[s['order']]))
            sortby2 = fes.SortBy(sorts)
        else:
            sortby2 = None

        if len(constraints) > 1:
            constraints = [fes.And(constraints)]

        LOGGER.debug(f'Querying CSW: {self.data}')
        csw = self._get_csw()
        try:
            csw.getrecords2(esn='full', maxrecords=limit, startposition=offset,
                            constraints=constraints, sortby=sortby2,
                            resulttype=resulttype)
        except ExceptionReport as err:
            msg = f'CSW error {err}'
            LOGGER.error(msg)
            raise ProviderQueryError(msg)

        response['numberMatched'] = csw.results['matches']
        response['numberReturned'] = csw.results['returned']
        LOGGER.debug(f"Found {response['numberMatched']} records")
        LOGGER.debug(f"Returned {response['numberReturned']} records")

        LOGGER.debug('Building result set')
        for record in csw.records.values():
            response['features'].append(self._owslibrecord2record(record))

        return response

    @crs_transform
    def get(self, identifier, **kwargs):
        """
        CSW GetRecordById query

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """

        csw = self._get_csw()
        csw.getrecordbyid([identifier], esn='full')

        if not csw.records:
            err = f'item {identifier} not found'
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)

        record_key = list(csw.records.keys())[0]

        return self._owslibrecord2record(csw.records[record_key])

    def _get_csw(self) -> CatalogueServiceWeb:
        """
        Helper function to lazy load a CSW

        returns: `owslib.csw.CatalogueServiceWeb`
        """

        try:
            return CatalogueServiceWeb(self.data)
        except Exception as err:
            err = f'CSW connection error: {err}'
            LOGGER.error(err)
            raise ProviderConnectionError(err)

    def _gen_getrecordbyid_link(self, identifier: str,
                                csw_version: str = '2.0.2') -> dict:
        """
        Helper function to generate a CSW GetRecordById URL

        :param identifier: `str` of record identifier
        :param csw_version: `str` of CSW version (default is `2.0.2`)

        :returns: `dict` of link object of GetRecordById URL
        """

        params = {
            'service': 'CSW',
            'version': csw_version,
            'request': 'GetRecordById',
            'id': identifier
        }

        return {
            'rel': 'alternate',
            'type': 'application/xml',
            'title': 'This document as XML',
            'href': f'{self.data}?{urlencode(params)}',
        }

    def _owslibrecord2record(self, record):
        LOGGER.debug(f'Transforming {record.identifier}')
        feature = {
            'id': record.identifier,
            'type': 'Feature',
            'geometry': None,
            'time': record.date or None,
            'properties': {},
            'links': [
                self._gen_getrecordbyid_link(record.identifier)
            ]
        }

        LOGGER.debug('Processing record mappings to properties')
        for key, value in self.record_mappings.items():
            prop_value = getattr(record, value[1])
            if prop_value not in [None, [], '']:
                feature['properties'][key] = prop_value

        if record.bbox is not None:
            LOGGER.debug('Adding bbox')
            bbox = [
                get_typed_value(record.bbox.minx),
                get_typed_value(record.bbox.miny),
                get_typed_value(record.bbox.maxx),
                get_typed_value(record.bbox.maxy)
            ]
            feature['geometry'] = bbox2geojsongeometry(bbox)

        if record.references:
            LOGGER.debug('Adding references as links')
            for link in record.references:
                feature['links'].append({
                    'title': link['scheme'],
                    'href': link['url']
                })
        if record.uris:
            LOGGER.debug('Adding URIs as links')
            for link in record.uris:
                feature['links'].append({
                    'title': link['name'],
                    'href': link['url']
                })

        return feature

    def __repr__(self):
        return f'<CSWFacadeProvider> {self.data}'
