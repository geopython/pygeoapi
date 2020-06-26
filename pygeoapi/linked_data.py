# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2019 Tom Kralidis
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
""" Linked data capabilities
Returns content as linked data representations
"""

import json
import logging
from operator import itemgetter

from pygeoapi.util import (
    is_url, filter_dict_by_key_value, dategetter, list_get
)

LOGGER = logging.getLogger(__name__)

def inspect_config(func):
    """
    Decorator that extracts useful configuration data from the API instance
    (assumed to be first argument of wrapped func)

    :params func: Wrapped function

    :returns: Wrapped function, with new kwargs added (dicts)
    """
    def inner(*args, **kwargs):
        cls = args[0]
        metadata = cls.config.get('metadata', {})
        return func(*args, **{
            'cfg': cls.config,
            'meta': metadata,
            'contact': metadata.get('contact', {}),
            'provider': metadata.get('provider', {}),
            'ident': metadata.get('identification', {},
            **kwargs)
        })
    return inner

@inspect_config
def _build_root_jsonld(cls, **kwargs):
    """
    Builds the pygeoapi root JSON-LD metadata, a https://schema.org/WebSite

    :returns: dict
    """
    LOGGER.debug('Creating JSON-LD representation for root')
    cfg, meta, contact, provider, ident = itemgetter(
        'cfg', 'meta', 'contact', 'provider', 'ident'
    )(kwargs)
    return {
        "@context": {
            "schema": "https://schema.org/",
            "url": "schema:url"
        },
        "@type": "schema:WebSite",
        "@id": cfg['server'].get('pid', cfg['server']['url']),
        "schema:url": cfg['server']['url'],
        "schema:name": ident.get('title', None),
        "schema:description": ident.get('description', None),
        # "termsOfService": ident.get('terms_of_service', None),
        "schema:license": {
            "@type": "schema:CreativeWork",
            **meta.get('license', {})
        },
        "schema:provider": {
            "@type": "schema:Organization", # TODO allow Person
            "schema:name": provider.get('name', None),
            "schema:url": provider.get('url', None),
            "schema:address": {
                "@type": "schema:PostalAddress",
                "schema:streetAddress": contact.get('address', None),
                "schema:postalCode": contact.get('postalcode', None),
                "schema:addressLocality": contact.get('city', None),
                "schema:addressRegion": contact.get('stateorprovince', None),
                "schema:addressCountry": contact.get('country', None)
            },
            "contactPoint": {
                "@type": "schema:Contactpoint",
                "schema:email": contact.get('email', None),
                "schema:telephone": contact.get('phone', None),
                "schema:faxNumber": contact.get('fax', None),
                "schema:url": contact.get('url', None),
                "schema:hoursAvailable": {
                    "schema:opens": contact.get('hours', None),
                    "schema:description": contact.get('instructions', None)
                },
                "schema:contactType": contact.get('role', None),
                "schema:description": contact.get('position', None)
            }
        }
    }

@inspect_config
def _build_collections_jsonld(cls, **kwargs):
    """
    Builds the /collection JSON-LD representation,
    a https://schema.org/DataCatalog

    Adopts recommendations from:
    https://developers.google.com/search/docs/data-types/dataset#publication

    :returns: dict
    """
    LOGGER.debug('Creating JSON-LD representation for collections')
    cfg, meta, contact, provider, ident = itemgetter(
        'cfg', 'meta', 'contact', 'provider', 'ident'
    )(kwargs)
    collections = filter_dict_by_key_value(cfg['resources'],
                                           'type', 'collection')
    id = "{}/collections".format(cfg['server']['url'])
    license = {
        "@type": "CreativeWork",
        **meta.get('license', {})
    }
    if 'url' in license:
        license['schema:url'] = license.pop('url')
    if 'name' in license:
        license['schema:name'] = license.pop('name')
    return {
        "@context": {
            "schema": "https://schema.org/"
        },
        "@type": "schema:DataCatalog",
        "@id": id, # TODO allow PID
        "schema:name": ident.get('title', None),
        "schema:description": ident.get('description', None),
        "schema:url": id,
        "schema:isPartOf": {
            "@type": "schema:WebSite",
            "@id": cfg['server'].get('pid', cfg['server']['url']),
            "schema:url": cfg['server']['url']
        },
        "schema:license": license,
        "schema:keywords": ident.get('keywords', None),
        "schema:dataset": list(
            map(
                lambda collectionId: _describe_collection(
                    cls, id, collectionId, collections[collectionId]
                ), collections
            )
        )
    }

@inspect_config
def _describe_collection(cls, parentId, collectionId, collection, **kwargs):
    """
    Builds the JSON-LD representation of a single /collection/{id},
    an instance of https://schema.org/Dataset, including some DataDownload
    distributions (links)

    Adopts recommendations from:
    https://developers.google.com/search/docs/data-types/dataset
    https://developers.google.com/search/docs/data-types/dataset#download

    In particular, a "link" for a dataset are considered a "distribution",
    which provide a mechanism to get the actual data (and not a landing page).
    A distribution must be of type DataDownload, and include an encodingFormat
    and a contentURL.

    :returns: dict
    """
    cfg, meta = itemgetter('cfg', 'meta')(kwargs)
    id = "{}/collections/{}".format(cfg['server']['url'], collectionId)

    interval = collection.get('extents', {}).get('temporal', {})
    interval = list(map(lambda d: dategetter(d, interval), ['begin', 'end']))

    spatial_extent = collection.get('extents', {}).get('spatial', {})
    bbox = spatial_extent.get('bbox', None)
    crs = spatial_extent.get('crs', None)
    hascrs84 = crs and crs.endswith('CRS84')

    links = []
    for _link in collection.get('links', []):
        link = {
            '@type': 'schema:DataDownload',
            'schema:encodingFormat': _link['type'],
            'schema:description': _link['title'],
            'schema:contentURL': _link['href']
        }
        if 'hreflang' in _link:
            link['schema:inLanguage'] = _link['hreflang']
        if 'rel' in link and link['rel'] == 'author':
            link['schema:author'] = {
                '@type': 'schema:Organization',
                'schema:url': _link['href']
            }
            link.pop('schema:contentURL')
        links.append(link)

    defaultLang = cfg['server'].get('language')
    links.append({
        "@type": "schema:DataDownload",
        'schema:encodingFormat': 'application/geo+json',
        'schema:description': 'Items as GeoJSON',
        'schema:contentURL': '{}/collections/{}/items?f=json'.format(
            cfg['server']['url'], collectionId),
        'schema:inLanguage': defaultLang
    })
    links.append({
        "@type": "schema:DataDownload",
        'schema:encodingFormat': 'application/ld+json',
        'schema:description': 'Items as RDF (GeoJSON-LD)',
        'schema:contentURL': '{}/collections/{}/items?f=jsonld'.format(
            cfg['server']['url'], collectionId),
        'schema:inLanguage': defaultLang
    })
    links.append({
        "@type": "schema:DataDownload",
        'schema:encodingFormat': 'text/html',
        'schema:description': 'Items as HTML',
        'schema:contentURL': '{}/collections/{}/items?f=html'.format(
            cfg['server']['url'], collectionId),
        'schema:inLanguage': defaultLang
    })

    sameAsLinks = [l['href'] for l in filter(lambda l: l['rel'] == 'canonical', collection.get('links', []))]

    license = collection.get('license', {}).get('url') or {
        "@type": "schema:CreativeWork",
        **meta.get('license', {})
    }
    if 'url' in license:
        license['schema:url'] = license.pop('url')
    if 'name' in license:
        license['schema:name'] = license.pop('name')
    return {
        "@type": "schema:Dataset",
        "@id": id, # TODO allow PID
        "schema:url": id,
        "schema:sameAs": sameAsLinks[0] if len(sameAsLinks) > 1 else (sameAsLinks or None),
        "schema:includedInDataCatalog": {
            "@id": parentId,
            "@type": "DataCatalog",
            "schema:url": parentId
        },
        "schema:isPartOf": {
            "@type": "schema:WebSite",
            "@id": cfg['server'].get('pid', cfg['server']['url']),
            "schema:url": cfg['server']['url']
        },
        "schema:name": collection['title'], # REQUIRED for Google Dataset Search
        "schema:description": collection['description'], # REQUIRED for Google Dataset Search
        "schema:license": license, # RECOMMENDED for Google Dataset Search
        "schema:keywords": collection.get('keywords'), # RECOMMENDED for Google Dataset Search
        "schema:spatialCoverage": None if (not hascrs84 or not bbox) else {
            "@type": "schema:Place",
            "schema:geo": {
                "@type": "schema:GeoShape",
                "schema:box": '{} {} {} {}'.format(*bbox)
            }
        },
        "schema:temporalCoverage": "{}/{}".format(*interval),
        "schema:distribution": links
    }

@inspect_config
def _build_queryables_jsonld(cls, queryables, dataset, **kwargs):
    """
    Builds the JSON-LD representation of the /collections/{id}/queryables,
    currently a https://schema.org/DefinedTermSet

    :returns: dict
    """
    # TODO while this keeps the JSON API contract, this still needs work
    # TODO inspect the collection context, if defined, same as GeoJSON
    cfg = itemgetter('cfg')(kwargs)
    return {
        "@context": [
            {
                "schema": "https://schema.org/",
                "queryables": "schema:definedTerm",
                "queryable": "schema:name"
            }
        ],
        "@type": "schema:DefinedTermSet",
        "@id": '{}/collections/{}/queryables'.format(
            cfg['server']['url'], dataset
        ),
        "schema:url": '{}/collections/{}/queryables'.format(
            cfg['server']['url'], dataset
        ),
        "schema:name": "queryables",
        "queryables": list(map(lambda q: {
            "@type": "DefinedTerm",
            "queryable": q['queryable']
        }, queryables.get('queryables', [])))
    }

def jsonldify(func):
    """
    Decorator that mutates app configuration
    to include a JSON-LD representation available as API.fcmld

    Note that this decorator depends on the wrapped function being known,
    with a dedicated branch within this function, it will otherwise be a no-op.

    For certain wrapped functions, especially functions that return GeoJSON
    data, this decorator instead post-processes the output into GeoJSON-LD.

    :param func: decorated function

    :returns: wrapped `func`, or the transformed output
              (response-headers, http-status, content)
    """

    def inner(*args, **kwargs):
        cls, headers, format_ = args[0:3]
        if not format_ == 'jsonld':
            return func(*args, **kwargs)

        fcmld = {}
        if func.__name__ == 'root':
            fcmld = {**fcmld, **_build_root_jsonld(cls)}
        elif func.__name__ == 'describe_collections':
            dataset = kwargs.get('dataset', None)
            if dataset:
                # Describe one collection
                _collections = {**fcmld, **_build_collections_jsonld(cls)}
                fcmld = {
                    '@context': {**_collections['@context']},
                    **next(iter([c for c in _collections.get('schema:dataset', []) if c['schema:url'].endswith('/{}'.format(dataset))]), {})
                }
            else:
                fcmld = {**fcmld, **_build_collections_jsonld(cls)}
        elif func.__name__ == 'get_collection_queryables':
            responseHeaders, status, content = func(*args, **kwargs)
            dataset = kwargs.get('dataset', list_get(args, 4))
            if status != 200:
                return responseHeaders, status, content
            content = _build_queryables_jsonld(cls, content, dataset)
            return responseHeaders, status, content
        elif func.__name__ == 'get_stac_root':
            pass
        # elif func.__name__ == 'describe_processes':
        #     TODO WebAPI for processing
        #     LOGGER.debug('Creating JSON-LD representation for processes')
        #     if kwargs.get('process', None):
        #         # Describe all processes
        #         pass
        #     else:
        #         # Describe one process
        #         pass
        elif func.__name__ in ['get_collection_items', 'get_collection_item']:
            # Let func run unchanged, and then intercept output
            # This allows this decorator to inherit any applied filters
            # before transforming GeoJSON to (Geo)JSON-LD
            responseHeaders, status, content = func(*args, **kwargs)
            if status != 200:
                return responseHeaders, status, content
            dataset = kwargs.get('dataset', list_get(args, 4))
            identifier = kwargs.get('identifier', list_get(args, 5))
            content = _geojson_transform_jsonld(
                cls.config, content, dataset, identifier=identifier
            )
            return responseHeaders, status, content

        else:
            # No handler: no-op
            return func(*args, **kwargs)

        cls.fcmld = fcmld
        return func(cls, *args[1:], **kwargs)
    return inner

# TODO
# def jsonldify_process(cls, process=None):
#     """
#     Transform process into a JSON-LD representation
#
#     :param cls: API object
#     :param collection: `process` as prepared for non-LD JSON
#                        representation
#
#     :returns: `process` a dictionary, mapped into JSON-LD, of
#               type schema:WebAPI
#     """
#     # TODO look at https://schema.org/EntryPoint and https://schema.org/Action
#     # TODO consider http://www.hydra-cg.com/spec/latest/core/#discovering-a-hydra-powered-web-api
#     # print(process)
#     process_ld = {
#         "@type": "WebAPI", # TODO correct type?
#         "@id": "{}/processes/{}".format(
#             cls.config['server']['url'],
#             process['id']
#         ),
#         "name": process['title'],
#         "description": process['description'],
#         "url": "{}/processes/{}".format(
#             cls.config['server']['url'],
#             process['id']
#         ),
#         # TODO clarify this
#         # TODO link.rel
#         "documentation": list(map(lambda link: {
#             "@type": "URL",
#             "url": link['href']
#         }, process.get('links', [])))
#         # TODO parameters?
#         # process.inputs [id, name, description, etc.]
#     }
#     return process_ld

def _geojson_transform_jsonld(config, data, dataset, identifier=None):
    """
    Render GeoJSON-LD from a GeoJSON base. Inserts a @context that can be
    read from, and extended by, the pygeoapi configuration for a particular
    dataset.

    :param config: dict of configuration
    :param data: dict of data
    :param dataset: dataset identifier
    :param identifier: item identifier (optional)

    :returns: string of rendered JSON (GeoJSON-LD)
    """
    context = config['resources'][dataset].get('context', [])
    uri_field = config['resources'][dataset].get('provider', {}).get('uri_field', None)
    id_field = config['resources'][dataset].get('provider', {}).get('id_field', None)

    _data = {**data}
    _data.pop('links', None)

    host = config['server']['url']

    isCollection = identifier is None
    url_base = '{}/collections/{}/items'.format(host, dataset)
    fallback_url = '{}/{}'.format(url_base, identifier)

    if isCollection:
        for feature in _data['features']:
            feature['properties']['id'] = feature['id']
            if feature['geometry']['type'] == 'Point': continue
            feature.pop('geometry')
    else:
        if _data['geometry']['type'] != 'Point':
            _data.pop('geometry')
        _data['properties']['id'] = _data['id']

    if _data.get('timeStamp', False):
        _data['https://schema.org/sdDatePublished'] = _data.pop('timeStamp')

    # NOTE: non-point geometries are dropped from JSON-LD output
    inlinedVocabulary = {
        "schema": "https://schema.org/",
        "geojson": "https://purl.org/geojson/vocab#",
        "Feature": "geojson:Feature",
        "FeatureCollection": "geojson:FeatureCollection",
        # "GeometryCollection": "geojson:GeometryCollection",
        # "LineString": "geojson:LineString",
        # "MultiLineString": "geojson:MultiLineString",
        # "MultiPoint": "geojson:MultiPoint",
        # "MultiPolygon": "geojson:MultiPolygon",
        "Point": "geojson:Point",
        # "Polygon": "geojson:Polygon",
        "bbox": {
            "@container": "@list",
            "@id": "geojson:bbox"
        },
        "coordinates": {
            "@container": "@list",
            "@id": "geojson:coordinates"
        },
        "features": {
            "@container": "@set",
            "@id": "geojson:features"
        },
        "geometry": "geojson:geometry",
        "id": "@id",
        "properties": "geojson:properties",
        "type": "@type",
    } # inlined, see https://github.com/geopython/pygeoapi/issues/457

    ldjsonData = {
        "@context": [
            # "https://geojson.org/geojson-ld/geojson-context.jsonld",
            inlinedVocabulary,
            *(context or [])
        ],
        **_data
    }

    return json.dumps(ldjsonData)
