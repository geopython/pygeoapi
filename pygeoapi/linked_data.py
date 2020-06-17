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
def _build_root_jsonld(**kwargs):
    """
    Builds the pygeoapi root JSON-LD metadata, a https://schema.org/WebSite

    :returns: dict
    """
    LOGGER.debug('Creating JSON-LD representation for root')
    cfg, meta, contact, provider, ident = itemgetter(
        'cfg', 'meta', 'contact', 'provider', 'ident'
    )(kwargs)
    return {
        # "@context": "https://schema.org/docs/jsonldcontext.jsonld",
        "@context": [
            "https://schema.org",
            {
                "title": "name" # To keep API consistent with ordinary JSON interface
            }
        ],
        "@type": "WebSite",
        "@id": cfg['server'].get('pid', cfg['server']['url']),
        "url": cfg['server']['url'],
        "title": ident.get('title', None),
        "description": ident.get('description', None),
        # "termsOfService": ident.get('terms_of_service', None),
        "license": {
            "@type": "CreativeWork",
            **meta.get('license', {})
        },
        "provider": {
            "@type": "Organization", # TODO allow Person
            "name": provider.get('name', None),
            "url": provider.get('url', None),
            "address": {
                "@type": "PostalAddress",
                "streetAddress": contact.get('address', None),
                "postalCode": contact.get('postalcode', None),
                "addressLocality": contact.get('city', None),
                "addressRegion": contact.get('stateorprovince', None),
                "addressCountry": contact.get('country', None)
            },
            "contactPoint": {
                "@type": "Contactpoint",
                "email": contact.get('email', None),
                "telephone": contact.get('phone', None),
                "faxNumber": contact.get('fax', None),
                "url": contact.get('url', None),
                "hoursAvailable": {
                    "opens": contact.get('hours', None),
                    "description": contact.get('instructions', None)
                },
                "contactType": contact.get('role', None),
                "description": contact.get('position', None)
            }
        }
    }

@inspect_config
def _build_collections_jsonld(**kwargs):
    """
    Builds the /collection JSON-LD representation,
    a https://schema.org/DataCatalog

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
    return {
        "@context": [
            "https://schema.org",
            {
                "collections": "dataset",
                "links": "distribution"
            } # To keep API consistent with ordinary JSON interface
        ],
        "@type": "DataCatalog",
        "@id": id, # TODO allow PID
        "url": id,
        "isPartOf": {
            "@type": "WebSite",
            "@id": cfg['server'].get('pid', cfg['server']['url']),
            "url": cfg['server']['url']
        },
        "license": license,
        "keywords": ident.get('keywords', None),
        "collections": list(
            map(
                lambda collectionId: _describe_collection(
                    cls, id, collectionId, collections[collectionId]
                ), collections
            )
        )
    }

@inspect_config
def _describe_collection(cls, parentId, collectionId, collection):
    """
    Builds the JSON-LD representation of a single /collection/{id},
    an instance of https://schema.org/Dataset, including some DataDownload
    distributions (links)

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
            '@type': 'DataDownload',
            'encodingFormat': _link['type'],
            'description': _link['title'],
            'contentURL': _link['href']
        }
        if 'hreflang' in _link:
            link['inLanguage'] = _link['hreflang']
        links.append(link)

    defaultLang = cfg['server'].get('language')
    links.append({
        "@type": "DataDownload",
        'encodingFormat': 'application/geo+json',
        'description': 'Items as GeoJSON',
        'contentURL': '{}/collections/{}/items?f=json'.format(
            cfg['server']['url'], collectionId),
        'inLanguage': defaultLang
    })
    links.append({
        "@type": "DataDownload",
        'encodingFormat': 'application/ld+json',
        'description': 'Items as RDF (GeoJSON-LD)',
        'contentURL': '{}/collections/{}/items?f=jsonld'.format(
            cfg['server']['url'], collectionId),
        'inLanguage': defaultLang
    })
    links.append({
        "@type": "DataDownload",
        'encodingFormat': 'text/html',
        'description': 'Items as HTML',
        'contentURL': '{}/collections/{}/items?f=html'.format(
            cfg['server']['url'], collectionId),
        'inLanguage': defaultLang
    })

    return {
        "@context": [
            "https://schema.org",
            {
                "links": "distribution"
            } # To keep API consistent with ordinary JSON interface
        ],
        "@type": "Dataset",
        "@id": id, # TODO allow PID
        "url": id,
        "includedInDataCatalog": {
            "@id": parentId,
            "@type": "DataCatalog",
            "url": parentId
        },
        "isPartOf": {
            "@type": "WebSite",
            "@id": cfg['server'].get('pid', cfg['server']['url']),
            "url": cfg['server']['url']
        },
        "name": collection['title'], # REQUIRED for Google Dataset Search
        "description": collection['description'], # REQUIRED for Google Dataset Search
        "license": collection.get('license', {}).get('url') or {
            "@type": "CreativeWork",
            **meta.get('license', {})
        }, # RECOMMENDED for Google Dataset Search
        "keywords": collection.get('keywords'), # RECOMMENDED for Google Dataset Search
        "spatialCoverage": None if (not hascrs84 or not bbox) else {
            "@type": "Place",
            "geo": {
                "@type": "GeoShape",
                "box": '{} {} {} {}'.format(*bbox)
            }
        },
        "temporalCoverage": "{}/{}".format(*interval),
        "links": links
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
    LOGGER.debug(queryables)
    LOGGER.debug(type(queryables))
    LOGGER.debug([cls, dataset, cfg])
    return {
        "@context": [
            "https://schema.org",
            {
                "queryables": "definedTerm",
                "queryable": "name"
            }
        ],
        "@type": "DefinedTermSet",
        "@id": '{}/collections/{}/queryables'.format(
            cfg['server']['url'], dataset
        ),
        "url": '{}/collections/{}/queryables'.format(
            cfg['server']['url'], dataset
        ),
        "name": "queryables",
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
            dataset = kwargs.get('dataset', list_get(args, 3))
            if dataset:
                # Describe one collection
                _collections = {**fcmld, **_build_collections_jsonld(cls)}.get('collections', [])
                fcmld = next(iter([c for c in _collections if c['url'].endswith('/{}'.format(dataset))]), {})
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
            content = geojson2geojsonld(
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

def geojson2geojsonld(config, data, dataset, identifier=None):
    """
    Render GeoJSON-LD from a GeoJSON base. Inserts a @context that can be
    read from, and extended by, the pygeoapi configuration for a particular
    dataset.

    :param config: dict of configuration
    :param data: dict of data:
    :param dataset: dataset identifier
    :param identifier: item identifier (optional)

    :returns: string of rendered JSON (GeoJSON-LD)
    """
    context = config['resources'][dataset].get('context', [])
    data['id'] = (
        '{}/collections/{}/items/{}' if identifier
        else '{}/collections/{}/items'
    ).format(
        *[config['server']['url'], dataset, identifier]
    )
    if data.get('timeStamp', False):
        data['https://schema.org/sdDatePublished'] = data.pop('timeStamp')

    # defaultVocabulary = "https://geojson.org/geojson-ld/geojson-context.jsonld"
    defaultVocabulary = {
        "geojson": "https://purl.org/geojson/vocab#",
        "Feature": "geojson:Feature",
        "FeatureCollection": "geojson:FeatureCollection",
        "GeometryCollection": "geojson:GeometryCollection",
        "LineString": "geojson:LineString",
        "MultiLineString": "geojson:MultiLineString",
        "MultiPoint": "geojson:MultiPoint",
        "MultiPolygon": "geojson:MultiPolygon",
        "Point": "geojson:Point",
        "Polygon": "geojson:Polygon",
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
        "@context": [defaultVocabulary, *(context or [])],
        **data
    }
    isCollection = identifier is None
    if isCollection:
        for i, feature in enumerate(data['features']):
            featureId = feature.get(
                'id', None
            ) or feature.get('properties', {}).get('id', None)
            if featureId is None:
                continue
            # Note: @id or https://schema.org/url or both or something else?
            if is_url(str(featureId)):
                feature['id'] = featureId
            else:
                feature['id'] = '{}/{}'.format(data['id'], featureId)

    return json.dumps(ldjsonData)
