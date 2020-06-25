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

from pygeoapi.util import is_url

LOGGER = logging.getLogger(__name__)


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
          "@context": {
              "schema": "https://schema.org/"
          },
          "@type": "schema:DataCatalog",
          "@id": cfg.get('server', {}).get('url', None),
          "schema:url": cfg.get('server', {}).get('url', None),
          "schema:name": ident.get('title', None),
          "schema:description": ident.get('description', None),
          "schema:keywords": ident.get('keywords', None),
          "schema:termsOfService": ident.get('terms_of_service', None),
          "schema:license": meta.get('license', {}).get('url', None),
          "schema:provider": {
            "@type": "schema:Organization",
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
        "@type": "schema:Dataset",
        "@id": "{}/collections/{}".format(
            cls.config['server']['url'],
            collection['id']
        ),
        "schema:name": collection['title'],
        "schema:description": collection['description'],
        "schema:license": cls.fcmld['schema:license'],
        "schema:keywords": collection.get('keywords', None),
        "schema:spatial": None if (not hascrs84 or not bbox) else [{
            "@type": "schema:Place",
            "schema:geo": {
                "@type": "schema:GeoShape",
                "schema:box": '{},{} {},{}'.format(*_bbox[0:2], *_bbox[2:4])
            }
        } for _bbox in bbox],
        "schema:temporalCoverage": None if not interval else "{}/{}".format(
            *interval[0]
        )
    }
    dataset['schema:url'] = dataset['@id']

    links = collection.get('links', [])

    if links:
        dataset['schema:distribution'] = \
            list(map(lambda link: {k: v for k, v in {
                "@type": "schema:DataDownload",
                "schema:contentURL": link['href'],
                "schema:encodingFormat": link['type'],
                "schema:description": link['title'],
                "schema:inLanguage": link.get(
                    'schema:hreflang', cls.config.get('server', {})
                    .get('language', None)
                ),
                "schema:author": link['rel'] if link.get(
                    'rel', None
                ) == 'author' else None
            }.items() if v is not None}, links))

    return dataset


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

    # Currently "uri" is a magic property, eventually we should have this
    # be in the config so a user can override the use of a URI.
    uri = data.get('properties', {}).get('uri', None)

    if identifier and uri:
        data['id'] = '{}'.format(uri)
    elif identifier:
        data['id'] = '{}/collections/{}/items/{}'\
            .format(config['server']['url'], dataset, identifier)
    else:
        data['id'] = '{}/collections/{}/items'\
            .format(config['server']['url'], dataset)

    if data.get('timeStamp', False):
        data['https://schema.org/sdDatePublished'] = data.pop('timeStamp')

    default_vocabulary = {
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
    }

    jsonld_data = {
        "@context": [default_vocabulary, *(context or [])],
        **data
    }

    if 'schema' not in jsonld_data['@context']:
        jsonld_data['@context'].append({"schema": "https://schema.org"})

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
                feature_uri = feature.get('properties', {}).get('uri', None)
                feature['id'] = feature_uri or '{}/{}' \
                    .format(data['id'], featureId)
    else:
        if jsonld_data["geometry"]["type"] != "Point":
            jsonld_data["geometry"] = {
                "schema:encodingFormat": "application/geo+json",
                "schema:url": data['id'] + '?f=json'}

    return json.dumps(jsonld_data)
