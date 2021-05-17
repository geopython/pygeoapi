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

import logging

from pygeoapi.util import is_url
from shapely.geometry import asShape
from shapely.ops import unary_union
from shapely import speedups

LOGGER = logging.getLogger(__name__)
LOGGER.debug("Shapely Speedups enabled: {}".format(speedups.enabled))


def jsonldify(func):
    """
        Decorator that transforms app configuration\
        to include a JSON-LD representation

        :param func: decorated function

        :returns: `func`
    """

    def inner(*args, **kwargs):
        format_ = args[2]
        if not format_ == 'jsonld':
            return func(*args, **kwargs)
        LOGGER.debug('Creating JSON-LD representation')
        cls = args[0]
        cfg = cls.config
        meta = cfg.get('metadata', {})
        contact = meta.get('contact', {})
        provider = meta.get('provider', {})
        ident = meta.get('identification', {})
        fcmld = {
          "@context": "https://schema.org/docs/jsonldcontext.jsonld",
          "@type": "DataCatalog",
          "@id": cfg.get('server', {}).get('url', None),
          "url": cfg.get('server', {}).get('url', None),
          "name": ident.get('title', None),
          "description": ident.get('description', None),
          "keywords": ident.get('keywords', None),
          "termsOfService": ident.get('terms_of_service', None),
          "license": meta.get('license', {}).get('url', None),
          "provider": {
            "@type": "Organization",
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
        cls.fcmld = fcmld
        return func(cls, *args[1:], **kwargs)
    return inner


def jsonldify_collection(cls, collection):
    """
        Transforms collection into a JSON-LD representation

        :param cls: API object
        :param collection: `collection` as prepared for non-LD JSON
                           representation

        :returns: `collection` a dictionary, mapped into JSON-LD, of
                  type schema:Dataset
    """
    temporal_extent = collection.get('extent', {}).get('temporal', {})
    interval = temporal_extent.get('interval', [[None, None]])

    spatial_extent = collection.get('extent', {}).get('spatial', {})
    bbox = spatial_extent.get('bbox', None)
    crs = spatial_extent.get('crs', None)
    hascrs84 = crs.endswith('CRS84')

    dataset = {
        "@type": "Dataset",
        "@id": "{}/collections/{}".format(
            cls.config['server']['url'],
            collection['id']
        ),
        "name": collection['title'],
        "description": collection['description'],
        "license": cls.fcmld['license'],
        "keywords": collection.get('keywords', None),
        "spatial": None if (not hascrs84 or not bbox) else [{
            "@type": "Place",
            "geo": {
                "@type": "GeoShape",
                "box": '{},{} {},{}'.format(*_bbox[0:2], *_bbox[2:4])
            }
        } for _bbox in bbox],
        "temporalCoverage": None if not interval else "{}/{}".format(
            *interval[0]
        )
    }
    dataset['url'] = dataset['@id']

    links = collection.get('links', [])
    if links:
        dataset['distribution'] = list(map(lambda link: {k: v for k, v in {
            "@type": "DataDownload",
            "contentURL": link['href'],
            "encodingFormat": link['type'],
            "description": link['title'],
            "inLanguage": link.get(
                'hreflang', cls.config.get('server', {}).get('language', None)
            ),
            "author": link['rel'] if link.get(
                'rel', None
            ) == 'author' else None
        }.items() if v is not None}, links))

    return dataset


def geojson2geojsonld(config, data, dataset, identifier=None, id_field='id'):
    """
    Render GeoJSON-LD from a GeoJSON base. Inserts a @context that can be
    read from, and extended by, the pygeoapi configuration for a particular
    dataset.

    :param config: dict of configuration
    :param data: dict of data:
    :param dataset: dataset identifier
    :param identifier: item identifier (optional)
    :param id_field: item identifier_field (optional)

    :returns: string of rendered JSON (GeoJSON-LD)
    """
    context = config['resources'][dataset].get('context', []).copy()
    geojsonld = config['resources'][dataset].get('geojsonld', True)

    if identifier:
        # Single geojsonld
        if not geojsonld:
            context.append({
                "geosparql": "http://www.opengis.net/ont/geosparql#"})
            data = make_jsonld(data)
            data[id_field] = identifier
        else:
            data['id'] = identifier

    else:
        # Collection of geojsonld
        data['@id'] = '{}/collections/{}/items/'.format(
            config['server']['url'], dataset)

        for i, feature in enumerate(data['features']):
            identifier = feature.get(id_field,
                                     feature['properties'].get(id_field, ''))
            if not is_url(str(identifier)):
                identifier = '{}/collections/{}/items/{}'.format(
                    config['server']['url'], dataset, feature['id'])
            if not geojsonld:
                context = [{
                    "features": "schema:itemListElement",
                    "FeatureCollection": "schema:itemList"
                }, ]
                make_jsonld(feature.copy())
                # Note: @id or https://schema.org/url, both or something else?
                feature = {
                    id_field: identifier,
                    'type': 'schema:Place'
                }
            else:
                feature['id'] = identifier

            data['features'][i] = feature

    if data.get('timeStamp', False):
        data['https://schema.org/sdDatePublished'] = data.pop('timeStamp')
    data['links'] = data.pop('links')

    defaultVocabulary = "https://geojson.org/geojson-ld/geojson-context.jsonld"

    if not geojsonld:
        defaultVocabulary = {
            "schema": "https://schema.org/",
            id_field: "@id",
            "type": "@type"
        }

    ldjsonData = {
        "@context": [
            defaultVocabulary,
            *(context or [])
        ],
        **data
    }

    return ldjsonData


def make_jsonld(feature):
    feature['type'] = 'schema:Place'
    geo = feature.get('geometry')
    geom = asShape(geo)

    # Geosparql geometry
    feature["geosparql:hasGeometry"] = {
        "@type": "http://www.opengis.net/ont/sf#{}".format(geom.geom_type),
        "geosparql:asWKT": {
            "@type": "http://www.opengis.net/ont/geosparql#wktLiteral",
            "@value": "{}".format(geom.wkt)
        }
    }

    # Schema Geometry
    feature["schema:geo"] = geojson2schema(geom)

    # Expand properties block
    feature = {**feature, **feature.get('properties')}
    feature.pop('properties')

    return feature


# GeoJSON to Schema
def geojson2schema(geom):
    schema_geo = {"@type": "schema:GeoShape"}
    if geom.geom_type == 'Point':
        return {
            "@type": "schema:GeoCoordinates",
            "schema:longitude": geom.x,
            "schema:latitude": geom.y
        }
    elif geom.geom_type == 'MultiPoint':
        poly_geom = [(p.x, p.y) for p in geom.geoms]
        poly_geom.append(poly_geom[0])
    elif geom.geom_type == 'LineString':
        _ = ['{},{}'.format(x, y) for (x, y) in geom.coords[:]]
        schema_geo['schema:line'] = ' '.join(_)
        return schema_geo
    elif geom.geom_type == 'MultiLineString':
        points = list()
        [points.extend(p.coords[:]) for p in geom.geoms]
        _ = ['{},{}'.format(x, y) for (x, y) in points]
        schema_geo['schema:line'] = ' '.join(_)
        return schema_geo
    elif geom.geom_type == 'Polygon':
        poly_geom = geom.exterior.coords[:]
    elif geom.geom_type == 'MultiPolygon':
        poly = unary_union(geom.buffer(0))
        if poly.geom_type.startswith('Multi') or not poly.is_valid:
            LOGGER.debug('Invalid Poly: {}'.format(poly.geom_type))
            poly = poly.convex_hull
            LOGGER.debug('New Poly: {}'.format(poly.geom_type))
        poly_geom = poly.exterior.coords[:]
    else:
        poly_geom = list()
        for p in geom.geoms:
            try:
                poly_geom.extend(p.coords[:])
            except NotImplementedError:
                poly_geom.extend(p.exterior.coords[:])

    LOGGER.debug(poly_geom)
    _ = ['{},{}'.format(*row) for row in poly_geom]
    schema_geo['schema:polygon'] = ' '.join(_)

    return schema_geo
