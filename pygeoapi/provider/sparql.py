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

import logging
from pygeoapi.plugin import load_plugin
from pygeoapi.provider.base import (ProviderQueryError,
                                    ProviderNoDataError, BaseProvider)
from pygeoapi.util import is_url
from SPARQLWrapper import SPARQLWrapper, JSON

LOGGER = logging.getLogger(__name__)

_PREFIX = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX : <http://dbpedia.org/resource/>
PREFIX dbpedia2: <http://dbpedia.org/property/>
PREFIX dbpedia: <http://dbpedia.org/>
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""

_SELECT = 'SELECT DISTINCT *'

_WHERE = """
WHERE {{
    VALUES ?v {{ {value} }}
    {where}
}}
"""


class SPARQLProvider(BaseProvider):
    """SPARQL Wrapper API Provider
    """
    def __init__(self, provider_def):
        """
        Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data, id_field, name set in parent class

        :returns: pygeoapi.provider.base.SPARQLProvider
        """
        super().__init__(provider_def)
        _provider_def = provider_def.copy()
        _provider_def['name'] = _provider_def.pop('sparql_provider')

        self.p = load_plugin('provider', _provider_def)
        self.sparql_endpoint = provider_def.get('sparql_endpoint')
        self.subj = provider_def.get('sparql_subject')
        self.predicates = provider_def.get('sparql_predicates')

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None):
        """
        SPARQL query
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
        content = self.p.query(startindex,
                               limit, resulttype, bbox,
                               datetime_, properties, sortby,
                               select_properties, skip_geometry, q)

        v = []
        for c in content['features']:
            subj, _ = self._clean_subj(c['properties'], self.subj)
            v.append(subj)

        search = ' '.join(v)
        values = self._sparql(search)

        for item in content['features']:
            _, _subj = self._clean_subj(item['properties'], self.subj)

            item['properties'] = self._combine(
                item['properties'], values.get(_subj)
            )

        return content

    def get(self, identifier):
        """
        Query by id
        :param identifier: feature id
        :returns: dict of single GeoJSON fea
        """
        LOGGER.debug(f'SPARQL for: {identifier}')
        feature = self.p.get(identifier)

        subj, _subj = self._clean_subj(feature['properties'], self.subj)

        values = self._sparql(subj)
        feature['properties'] = self._combine(
            feature['properties'], values.get(_subj)
        )

        return feature

    def _sparql(self, value):
        """
        Private function to request SPARQL context
        :param value: subject for SPARQL query
        :returns: dict of SPARQL feature data
        """
        LOGGER.debug('Requesting SPARQL data')

        w = ['OPTIONAL {{?v {p} ?{o} .}}'.format(p=v, o=k)
             for k, v in self.predicates.items()]
        where = ' '.join(w)

        qs = self._makeQuery(value, where)
        result = self._sendQuery(qs)

        return self._clean_result(result)

    def _clean_subj(self, properties, _subject):
        """
        Private function to clean SPARQL subject and return subject value
        :param properties: feature properties block
        :param _subject: subject field in properties block
        :param _subject: subject field in properties block
        :returns: subject value for properties block & SPARQL
        """
        if ":" in _subject:
            (_pref, _subject) = _subject.split(':')
        else:
            _pref = ''

        _subj = properties[_subject]
        if is_url(_subj):
            subj = f'<{_subj}>'
        elif is_url(_subj[1:-1]):
            subj = _subj
            _subj = subj[1:-1]
        elif _pref:
            __subj = _subj.replace(' ', '_')
            subj = f'{_pref}:{__subj}'
            if _pref == ' ':
                _subj = f'http://dbpedia.org/resource/{__subj}'

        return subj, _subj

    def _clean_result(self, result, ret={}):
        """
        Private function to clean SPARQL JSON result
        :param result: SPARQL response JSON
        :param ret: parsed return JSON
        :returns: dict of SPARQL feature results
        """
        for v in result['results']['bindings']:
            _id = v.pop('v').get('value')

            if not ret.get(_id, ''):
                ret[_id] = v

            for _k, _v in v.items():
                if not isinstance(ret[_id][_k], list):
                    ret[_id][_k] = [ret[_id][_k], ]

                _ = [_['value'] == _v['value'] for _ in ret[_id][_k]]
                if True not in _:
                    ret[_id][_k].append(_v)

        return ret

    def _combine(self, properties, results):
        """
        Private function to add SPARQL context to feature properties
        :param properties: dict of feature properties
        :param results: SPARQL data of feature
        :returns: dict of feature properties with SPARQL
        """
        try:
            for r in results:
                all_r = [_.get('value') for _ in results[r]]
                properties[r] = all_r[-1] if len(all_r) == 1 else all_r
        except TypeError as err:
            LOGGER.error('Error SPARQL data: {}'.format(err))
            raise ProviderNoDataError(err)
        return properties

    def _makeQuery(self, value, where, prefix=_PREFIX, select=_SELECT):
        """
        Private function to make SPARQL querystring
        :param value: str, collection of SPARQL subjects
        :param where: str, collection of SPARQL predicates
        :param prefix: str, Optional SPARQL prefixes (Default = _PREFIX)
        :param select: str, Optional SPARQL select
        :returns: str, SPARQL query
        """
        querystring = ''.join([
            prefix, select, _WHERE.format(value=value, where=where)
        ])
        LOGGER.debug('SPARQL query: {}'.format(querystring))

        return querystring

    def _sendQuery(self, query):
        """
        Private function to send SPARQL query
        :param query: str, SPARQL query
        :returns: SPARQL query results
        """
        LOGGER.debug('Sending SPARQL query')
        sparql = SPARQLWrapper(self.sparql_endpoint)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)

        try:
            results = sparql.query().convert()
            LOGGER.debug('Received SPARQL results')
        except Exception as err:
            LOGGER.error('Error in SPARQL query: {}'.format(err))
            raise ProviderQueryError(err)

        return results

    def get_fields(self):
        return self.p.get_fields()

    def get_data_path(self, baseurl, urlpath, dirpath):
        return self.p.get_data_path(baseurl, urlpath, dirpath)

    def get_metadata(self):
        return self.p.get_metadata()

    def create(self, new_feature):
        return self.p.creat(new_feature)

    def update(self, identifier, new_feature):
        return self.p.update(identifier, new_feature)

    def get_coverage_domainset(self):
        return self.p.get_coverage_domainset()

    def get_coverage_rangetype(self):
        return self.p.get_coverage_rangetype()

    def delete(self, identifier):
        return self.p.delete(identifier)

    def __repr__(self):
        return '<SPARQLProvider> {}, {}'.format(self.data, self.table)
