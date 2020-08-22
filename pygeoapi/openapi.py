# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
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
import logging
import os

import click
import yaml
import copy

from pygeoapi.plugin import load_plugin
from pygeoapi.util import (filter_dict_by_key_value, get_provider_by_type,
                           yaml_load)

LOGGER = logging.getLogger(__name__)

OPENAPI_YAML = {
    'oapif': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml',  # noqa
    'oapip': 'https://raw.githubusercontent.com/opengeospatial/wps-rest-binding/master/core/openapi'  # noqa
}


def get_ogc_schemas_location(server_config):

    osl = server_config.get('ogc_schemas_location', None)

    value = 'http://schemas.opengis.net'

    if osl is not None:
        if osl.startswith('http'):
            value = osl
        elif osl.startswith('/'):
            value = os.path.join(server_config['url'], 'schemas')

    return value


# TODO: remove this function once OGC API - Processing is final
def gen_media_type_object(media_type, api_type, path):
    """
    Generates an OpenAPI Media Type Object

    :param media_type: MIME type
    :param api_type: OGC API type
    :param path: local path of OGC API parameter or schema definition

    :returns: `dict` of media type object
    """

    ref = '{}/{}'.format(OPENAPI_YAML[api_type], path)

    content = {
        media_type: {
            'schema': {
                '$ref': ref
            }
        }
    }

    return content


# TODO: remove this function once OGC API - Processing is final
def gen_response_object(description, media_type, api_type, path):
    """
    Generates an OpenAPI Response Object

    :param description: text description of response
    :param media_type: MIME type
    :param api_type: OGC API type

    :returns: `dict` of response object
    """

    response = {
        'description': description,
        'content': gen_media_type_object(media_type, api_type, path)
    }

    return response


def get_oas_30(cfg):
    """
    Generates an OpenAPI 3.0 Document

    :param cfg: configuration object

    :returns: OpenAPI definition YAML dict
    """

    paths = {}

    osl = get_ogc_schemas_location(cfg['server'])
    OPENAPI_YAML['oapif'] = os.path.join(osl, 'ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml')  # noqa

    LOGGER.debug('setting up server info')
    oas = {
        'openapi': '3.0.2',
        'tags': []
    }
    info = {
        'title': cfg['metadata']['identification']['title'],
        'description': cfg['metadata']['identification']['description'],
        'x-keywords': cfg['metadata']['identification']['keywords'],
        'termsOfService':
            cfg['metadata']['identification']['terms_of_service'],
        'contact': {
            'name': cfg['metadata']['provider']['name'],
            'url': cfg['metadata']['provider']['url'],
            'email': cfg['metadata']['contact']['email']
        },
        'license': {
            'name': cfg['metadata']['license']['name'],
            'url': cfg['metadata']['license']['url']
        },
        'version': '3.0.2'
    }
    oas['info'] = info

    oas['servers'] = [{
        'url': cfg['server']['url'],
        'description': cfg['metadata']['identification']['description']
    }]

    paths['/'] = {
        'get': {
            'summary': 'Landing page',
            'description': 'Landing page',
            'tags': ['server'],
            'operationId': 'getLandingPage',
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                '200': {'$ref': '{}#/components/responses/LandingPage'.format(OPENAPI_YAML['oapif'])},  # noqa
                '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
            }
        }
    }

    paths['/openapi'] = {
        'get': {
            'summary': 'This document',
            'description': 'This document',
            'tags': ['server'],
            'operationId': 'getOpenapi',
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                '200': {'$ref': '#/components/responses/200'},
                '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                'default': {'$ref': '#/components/responses/default'}
            }
        }
    }

    paths['/conformance'] = {
        'get': {
            'summary': 'API conformance definition',
            'description': 'API conformance definition',
            'tags': ['server'],
            'operationId': 'getConformanceDeclaration',
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                '200': {'$ref': '{}#/components/responses/ConformanceDeclaration'.format(OPENAPI_YAML['oapif'])},  # noqa
                '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
            }
        }
    }

    paths['/collections'] = {
        'get': {
            'summary': 'Collections',
            'description': 'Collections',
            'tags': ['server'],
            'operationId': 'getCollections',
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                '200': {'$ref': '{}#/components/responses/Collections'.format(OPENAPI_YAML['oapif'])},  # noqa
                '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
            }
        }
    }

    oas['tags'].append({
            'name': 'server',
            'description': cfg['metadata']['identification']['description'],
            'externalDocs': {
                'description': 'information',
                'url': cfg['metadata']['identification']['url']}
        }
    )
    oas['tags'].append({
            'name': 'stac',
            'description': 'SpatioTemporal Asset Catalog'
        }
    )

    oas['components'] = {
        'responses': {
            '200': {
                'description': 'successful operation',
            },
            'default': {
                'description': 'Unexpected error',
                'content': gen_media_type_object('application/json', 'oapip', 'schemas/exception.yaml')  # noqa
            },
            'Queryables': {
                'description': 'successful queryables operation',
                'content': {
                    'application/json': {
                        'schema': {'$ref': '#/components/schemas/queryables'}
                    }
                }
            }
        },
        'parameters': {
            'f': {
                'name': 'f',
                'in': 'query',
                'description': 'The optional f parameter indicates the output format which the server shall provide as part of the response document.  The default format is GeoJSON.',  # noqa
                'required': False,
                'schema': {
                    'type': 'string',
                    'enum': ['json', 'html', 'jsonld'],
                    'default': 'json'
                },
                'style': 'form',
                'explode': False
            },
            'sortby': {
                'name': 'sortby',
                'in': 'query',
                'description': 'The optional sortby parameter indicates the sort property and order on which the server shall present results in the response document using the convention `sortby=PROPERTY:X`, where `PROPERTY` is the sort property and `X` is the sort order (`A` is ascending, `D` is descending). Sorting by multiple properties is supported by providing a comma-separated list.',  # noqa
                'required': False,
                'schema': {
                    'type': 'string',
                },
                'style': 'form',
                'explode': False
            },
            'startindex': {
                'name': 'startindex',
                'in': 'query',
                'description': 'The optional startindex parameter indicates the index within the result set from which the server shall begin presenting results in the response document.  The first element has an index of 0 (default).',  # noqa
                'required': False,
                'schema': {
                    'type': 'integer',
                    'minimum': 0,
                    'default': 0
                },
                'style': 'form',
                'explode': False
            }
        },
        'schemas': {
            # TODO: change this schema once OGC will definitively publish it
            'nameValuePairObj': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string'
                    },
                    'value': {
                        'oneOf':
                        [
                            {
                                'type': 'string'
                            },
                            {
                                'type': 'object'
                            }
                        ]
                    }
                }
            },
            'queryable': {
                'type': 'object',
                'required': [
                    'queryable',
                    'type'
                ],
                'properties': {
                    'queryable': {
                        'description': 'the token that may be used in a CQL predicate', # noqa
                        'type': 'string'
                    },
                    'title': {
                        'description': 'a human readable title for the queryable', # noqa
                        'type': 'string'
                    },
                    'description': {
                        'description': 'a human-readable narrative describing the queryable', # noqa
                        'type': 'string'
                    },
                    'language': {
                        'description': 'the language used for the title and description', # noqa
                        'type': 'string',
                        'default': [
                            'en'
                        ]
                    },
                    'type': {
                        'description': 'the data type of the queryable', # noqa
                        'type': 'string'
                    },
                    'type-ref': {
                        'description': 'a reference to the formal definition of the type', # noqa
                        'type': 'string',
                        'format': 'url'
                    }
                }
            },
            'queryables': {
                'type': 'object',
                'required': [
                    'queryables'
                ],
                'properties': {
                    'queryables': {
                        'type': 'array',
                        'items': {'$ref': '#/components/schemas/queryable'}
                    }
                }
            }
        }
    }

    items_f = deepcopy(oas['components']['parameters']['f'])
    items_f['schema']['enum'].append('csv')

    LOGGER.debug('setting up datasets')
    collections = filter_dict_by_key_value(cfg['resources'],
                                           'type', 'collection')

    for k, v in collections.items():

        # reset data transactions flag
        transaction = False

        collection_name_path = '/collections/{}'.format(k)
        tag = {
            'name': k,
            'description': v['description'],
            'externalDocs': {}
        }
        for link in v['links']:
            if link['type'] == 'information':
                tag['externalDocs']['description'] = link['type']
                tag['externalDocs']['url'] = link['url']
                break
        if len(tag['externalDocs']) == 0:
            del tag['externalDocs']

        oas['tags'].append(tag)

        paths[collection_name_path] = {
            'get': {
                'summary': 'Get collection metadata'.format(v['title']),  # noqa
                'description': v['description'],
                'tags': [k],
                'operationId': 'describe{}Collection'.format(k.capitalize()),
                'parameters': [
                    {'$ref': '#/components/parameters/f'}
                ],
                'responses': {
                    '200': {'$ref': '{}#/components/responses/Collection'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }
        data_provider = load_plugin('provider', get_provider_by_type(
                        collections[k]['providers'], 'feature'))
        id = data_provider.id_field
        samp_feat = data_provider.query()['features'][0]
        if id in samp_feat:
            samp_feat.pop(id)
        else:
            samp_feat['properties'].pop(id)
        samp_prop = samp_feat['properties']
        samp_geom = samp_feat['geometry']
        fields = data_provider.get_fields()
        prop = dict()
        for key in samp_prop:
            prop[key] = {'type': fields[key],
                         'example': samp_prop[key]}
        geom = samp_geom['type']
        oapif = OPENAPI_YAML['oapif']
        geom_schema = '{}#/components/schemas/{}GeoJSON'\
                      .format(oapif, geom.lower())
        geom = {'$ref': geom_schema}
        form = {
                    'type': {
                        'type': 'string',
                        'enum': ['Feature']
                    },
                    'geometry': geom,
                    'properties': {
                        'type': 'object',
                        'properties': prop
                    }
                }
        post_form = copy.deepcopy(form)
        feature_id = '{}#/components/parameters/featureId'.format(oapif)
        nvpo = '#/components/schemas/nameValuePairObj'

        # flag if data transactions is specified and enabled for the collection
        if 'extensions' in collections[k]:
            if 'transactions' in collections[k]['extensions']:
                if collections[k]['extensions']['transactions']:
                    transaction = True

        items_path = '{}/items'.format(collection_name_path)

        paths[items_path] = {
            'get': {
                'summary': 'Get {} items'.format(v['title']),
                'description': v['description'],
                'tags': [k],
                'operationId': 'get{}Features'.format(k.capitalize()),
                'parameters': [
                    items_f,
                    {'$ref': '{}#/components/parameters/bbox'.format(OPENAPI_YAML['oapif'])},  # noqa
                    {'$ref': '{}#/components/parameters/limit'.format(OPENAPI_YAML['oapif'])},  # noqa
                    {'$ref': '#/components/parameters/sortby'},
                    {'$ref': '#/components/parameters/startindex'}
                ],
                'responses': {
                    '200': {'$ref': '{}#/components/responses/Features'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }

        post = {
            'post': {
                'summary': 'Add a new feature to {}'.format(v['title']),
                'description': v['description'],
                'tags': [k],
                'requestBody': {
                    'required': True,
                    'content': {
                        'application/geo+json': {
                            'schema': {
                                'type': 'object',
                                'properties': post_form
                            }
                        }
                    }
                },
                'responses': {
                    '201': {
                        'description': 'Created {} item'.format(v['title']),
                        'headers': {
                            'Location': {
                                'schema': {
                                    'type': 'string'
                                }
                            }
                        }
                    },
                    '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }

        # if data transactions are enabled, add post
        if transaction:
            paths[items_path].update(post)

        p = load_plugin('provider', get_provider_by_type(
                        collections[k]['providers'], 'feature'))

        if p.fields:
            queryables_path = '{}/queryables'.format(collection_name_path)

            paths[queryables_path] = {
                'get': {
                    'summary': 'Get {} queryables'.format(v['title']),
                    'description': v['description'],
                    'tags': [k],
                    'operationId': 'get{}Queryables'.format(k.capitalize()),
                    'parameters': [
                        items_f,
                    ],
                    'responses': {
                        '200': {'$ref': '#/components/responses/Queryables'},
                        '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                    }
                }
            }

        if p.time_field is not None:
            paths[items_path]['get']['parameters'].append(
                {'$ref': '{}#/components/parameters/datetime'.format(OPENAPI_YAML['oapif'])})  # noqa

        for field, type in p.fields.items():

            if p.properties and field not in p.properties:
                LOGGER.debug('Provider specified not to advertise property')
                continue

            if type == 'date':
                schema = {
                    'type': 'string',
                    'format': 'date'
                }
            elif type == 'float':
                schema = {
                    'type': 'number',
                    'format': 'float'
                }
            elif type == 'long':
                schema = {
                    'type': 'integer',
                    'format': 'int64'
                }
            else:
                schema = {
                    'type': type
                }

            path_ = '{}/items'.format(collection_name_path)
            paths['{}'.format(path_)]['get']['parameters'].append({
                'name': field,
                'in': 'query',
                'required': False,
                'schema': schema,
                'style': 'form',
                'explode': False
            })

        paths['{}/items/{{featureId}}'.format(collection_name_path)] = {
            'get': {
                'summary': 'Get {} item by id'.format(v['title']),
                'description': v['description'],
                'tags': [k],
                'operationId': 'get{}Feature'.format(k.capitalize()),
                'parameters': [
                    {'$ref': '{}#/components/parameters/featureId'.format(OPENAPI_YAML['oapif'])},  # noqa
                    {'$ref': '#/components/parameters/f'}
                ],
                'responses': {
                    '200': {'$ref': '{}#/components/responses/Feature'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }
        samp_prop_pairs = samp_prop.items()
        pairs_iterator = iter(samp_prop_pairs)
        first_pair = next(pairs_iterator)
        samp_ext_kvp = [{'name': first_pair[0], 'value': first_pair[1]}]
        second_pair = next(pairs_iterator)
        samp_ext_keys = [second_pair[0]]
        samp_add_kvp = [{'name': 'item_name', 'value': 'item_value'}]
        patch = {
            'patch': {
                'summary': 'Update properties of an existing feature \
                    in {} by id'.format(v['title']),
                'description': v['description'],
                'tags': [k],
                'parameters': [
                    {'$ref': feature_id}
                ],
                'requestBody': {
                    'required': True,
                    'content': {
                        'application/json': {
                            'schema': {
                                'type': 'object',
                                'properties': {
                                    'add': {
                                        'type': 'array',
                                        'items': {
                                            '$ref': nvpo
                                        },
                                        'example': samp_add_kvp
                                    },
                                    'modify': {
                                        'type': 'array',
                                        'items': {
                                            '$ref': nvpo
                                        },
                                        'example': samp_ext_kvp
                                    },
                                    'remove': {
                                        'type': 'array',
                                        'items': {
                                            'type': 'string'
                                        },
                                        'example': samp_ext_keys
                                    }
                                }
                            }
                        }
                    }
                },
                'responses': {
                    '200': {
                        'description': 'Modified  {} item'.format(v['title']),
                        'headers': {
                            'Location': {
                                'schema': {
                                    'type': 'string',
                                }
                            }
                        },
                        'content': {
                            'application/geo+json': {
                                'schema': {
                                    '$ref': '{}#/components/schemas/featureGeoJSON'.format(OPENAPI_YAML['oapif'])  # noqa
                                }
                            }
                        }
                    },
                    '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }

        put = {
            'put': {
                'summary': 'Replace an existing feature in {} by id'
                .format(v['title']),
                'description': v['description'],
                'tags': [k],
                'parameters': [
                    {'$ref': feature_id}
                ],
                'requestBody': {
                    'required': True,
                    'content': {
                        'application/geo+json': {
                            'schema': {
                                'type': 'object',
                                'properties': form
                            }
                        }
                    }
                },
                'responses': {
                    '200': {'$ref': '#/components/responses/200'},  # noqa
                    '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }

        delete = {
            'delete': {
                'summary': 'Delete an existing feature from {} by id'.
                format(v['title']),
                'description': v['description'],
                'tags': [k],
                'parameters': [
                    {'$ref': feature_id}
                ],
                'responses': {
                    '200': {'$ref': '#/components/responses/200'},  # noqa
                    '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }

        # if data transactions are enabled, add patch, put and delete
        if transaction:
            fIdPath = '{}/items/{{featureId}}'.format(collection_name_path)
            for verb in [patch, put, delete]:
                paths[fIdPath].update(verb)

    LOGGER.debug('setting up STAC')
    stac_collections = filter_dict_by_key_value(cfg['resources'],
                                                'type', 'stac-collection')
    if stac_collections:
        paths['/stac'] = {
            'get': {
                'summary': 'SpatioTemporal Asset Catalog',
                'description': 'SpatioTemporal Asset Catalog',
                'tags': ['stac'],
                'operationId': 'getStacCatalog',
                'parameters': [],
                'responses': {
                    '200': {'$ref': '#/components/responses/200'},
                    'default': {'$ref': '#/components/responses/default'}
                }
            }
        }

    LOGGER.debug('setting up processes')
    processes = filter_dict_by_key_value(cfg['resources'], 'type', 'process')

    if processes:
        paths['/processes'] = {
            'get': {
                'summary': 'Processes',
                'description': 'Processes',
                'tags': ['server'],
                'operationId': 'getProcesses',
                'parameters': [
                    {'$ref': '#/components/parameters/f'}
                ],
                'responses': {
                    '200': {'$ref': '{}/responses/ProcessList.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                    'default': {'$ref': '#/components/responses/default'}
                }
            }
        }

        for k, v in processes.items():
            p = load_plugin('process', v['processor'])

            process_name_path = '/processes/{}'.format(k)
            tag = {
                'name': k,
                'description': p.metadata['description'],
                'externalDocs': {}
            }
            for link in p.metadata['links']:
                if link['type'] == 'information':
                    tag['externalDocs']['description'] = link['type']
                    tag['externalDocs']['url'] = link['url']
                    break
            if len(tag['externalDocs']) == 0:
                del tag['externalDocs']

            oas['tags'].append(tag)

            paths[process_name_path] = {
                'get': {
                    'summary': 'Get process metadata',
                    'description': p.metadata['description'],
                    'tags': [k],
                    'operationId': 'describe{}Process'.format(k.capitalize()),
                    'parameters': [
                        {'$ref': '#/components/parameters/f'}
                    ],
                    'responses': {
                        '200': {'$ref': '#/components/responses/200'},
                        'default': {'$ref': '#/components/responses/default'}
                    }
                }
            }
            paths['{}/jobs'.format(process_name_path)] = {
                'get': {
                    'summary': 'Retrieve job list for process',
                    'description': p.metadata['description'],
                    'tags': [k],
                    'operationId': 'get{}Jobs'.format(k.capitalize()),
                    'responses': {
                        '200': {'$ref': '#/components/responses/200'},
                        '404': {'$ref': '{}/responses/NotFound.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                        'default': {'$ref': '#/components/responses/default'}
                    }
                },
                'post': {
                    'summary': 'Process {} execution'.format(
                        p.metadata['title']),
                    'description': p.metadata['description'],
                    'tags': [k],
                    'operationId': 'execute{}Job'.format(k.capitalize()),
                    'parameters': [{
                        'name': 'response',
                        'in': 'query',
                        'description': 'Response type',
                        'required': False,
                        'schema': {
                            'type': 'string',
                            'enum': ['raw', 'document'],
                            'default': 'document'
                        }
                    }],
                    'responses': {
                        '200': {'$ref': '#/components/responses/200'},
                        '201': {'$ref': '{}/responses/ExecuteAsync.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                        '404': {'$ref': '{}/responses/NotFound.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                        '500': {'$ref': '{}/responses/ServerError.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                        'default': {'$ref': '#/components/responses/default'}
                    },
                    'requestBody': {
                        'description': 'Mandatory execute request JSON',
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    '$ref': '{}/schemas/execute.yaml'.format(OPENAPI_YAML['oapip'])  # noqa
                                }
                            }
                        }
                    }
                }
            }
            if 'example' in p.metadata:
                paths['{}/jobs'.format(process_name_path)]['post']['requestBody']['content']['application/json']['example'] = p.metadata['example']  # noqa

    oas['paths'] = paths

    return oas


def get_oas(cfg, version='3.0'):
    """
    Stub to generate OpenAPI Document

    :param cfg: configuration object
    :param version: version of OpenAPI (default 3.0)

    :returns: OpenAPI definition YAML dict
    """

    if version == '3.0':
        return get_oas_30(cfg)
    else:
        raise RuntimeError('OpenAPI version not supported')


@click.command('generate-openapi-document')
@click.pass_context
@click.option('--config', '-c', 'config_file', help='configuration file')
def generate_openapi_document(ctx, config_file):
    """Generate OpenAPI Document"""

    if config_file is None:
        raise click.ClickException('--config/-c required')
    with open(config_file) as ff:
        s = yaml_load(ff)
        click.echo(yaml.safe_dump(get_oas(s), default_flow_style=False))
