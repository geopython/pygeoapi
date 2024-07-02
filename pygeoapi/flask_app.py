# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Norman Barker <norman.barker@gmail.com>
#
# Copyright (c) 2024 Tom Kralidis
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

"""Flask module providing the route paths to the api"""

import os
from typing import Union

import click
from flask import (Flask, Blueprint, make_response, request,
                   send_from_directory, Response, Request)

from pygeoapi.api import API, APIRequest, apply_gzip
import pygeoapi.api.coverages as coverages_api
import pygeoapi.api.environmental_data_retrieval as edr_api
import pygeoapi.api.itemtypes as itemtypes_api
import pygeoapi.api.maps as maps_api
import pygeoapi.api.processes as processes_api
import pygeoapi.api.stac as stac_api
import pygeoapi.api.tiles as tiles_api
from pygeoapi.openapi import load_openapi_document
from pygeoapi.config import get_config
from pygeoapi.util import get_mimetype, get_api_rules


CONFIG = get_config()
OPENAPI = load_openapi_document()

API_RULES = get_api_rules(CONFIG)

if CONFIG['server'].get('admin'):
    from pygeoapi.admin import Admin

STATIC_FOLDER = 'static'
if 'templates' in CONFIG['server']:
    STATIC_FOLDER = CONFIG['server']['templates'].get('static', 'static')

APP = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path='/static')
APP.url_map.strict_slashes = API_RULES.strict_slashes

BLUEPRINT = Blueprint(
    'pygeoapi',
    __name__,
    static_folder=STATIC_FOLDER,
    url_prefix=API_RULES.get_url_prefix('flask')
)
ADMIN_BLUEPRINT = Blueprint('admin', __name__, static_folder=STATIC_FOLDER)

# CORS: optionally enable from config.
if CONFIG['server'].get('cors', False):
    try:
        from flask_cors import CORS
        CORS(APP)
    except ModuleNotFoundError:
        print('Python package flask-cors required for CORS support')

APP.config['JSONIFY_PRETTYPRINT_REGULAR'] = CONFIG['server'].get(
    'pretty_print', True)

api_ = API(CONFIG, OPENAPI)

OGC_SCHEMAS_LOCATION = CONFIG['server'].get('ogc_schemas_location')

if (OGC_SCHEMAS_LOCATION is not None and
        not OGC_SCHEMAS_LOCATION.startswith('http')):
    # serve the OGC schemas locally

    if not os.path.exists(OGC_SCHEMAS_LOCATION):
        raise RuntimeError('OGC schemas misconfigured')

    @BLUEPRINT.route('/schemas/<path:path>', methods=['GET'])
    def schemas(path):
        """
        Serve OGC schemas locally

        :param path: path of the OGC schema document

        :returns: HTTP response
        """

        full_filepath = os.path.join(OGC_SCHEMAS_LOCATION, path)
        dirname_ = os.path.dirname(full_filepath)
        basename_ = os.path.basename(full_filepath)

        path_ = dirname_.replace('..', '').replace('//', '').replace('./', '')

        if '..' in path_:
            return 'Invalid path', 400

        return send_from_directory(path_, basename_,
                                   mimetype=get_mimetype(basename_))


# TODO: inline in execute_from_flask when all views have been refactored
def get_response(result: tuple):
    """
    Creates a Flask Response object and updates matching headers.

    :param result: The result of the API call.
                   This should be a tuple of (headers, status, content).

    :returns: A Response instance
    """

    headers, status, content = result
    response = make_response(content, status)

    if headers:
        response.headers = headers
    return response


def execute_from_flask(api_function, request: Request, *args,
                       skip_valid_check=False) -> Response:
    """
    Executes API function from Flask

    :param api_function: API function
    :param request: request object
    :param *args: variable length additional arguments
    :param skip_validity_check: bool

    :returns: A Response instance
    """

    api_request = APIRequest.from_flask(request, api_.locales)

    content: Union[str, bytes]

    if not skip_valid_check and not api_request.is_valid():
        headers, status, content = api_.get_format_exception(api_request)
    else:
        headers, status, content = api_function(api_, api_request, *args)
        content = apply_gzip(headers, content)
        # handle jsonld too?

    return get_response((headers, status, content))


@BLUEPRINT.route('/')
def landing_page():
    """
    OGC API landing page endpoint

    :returns: HTTP response
    """
    return get_response(api_.landing_page(request))


@BLUEPRINT.route('/openapi')
def openapi():
    """
    OpenAPI endpoint

    :returns: HTTP response
    """

    return get_response(api_.openapi_(request))


@BLUEPRINT.route('/conformance')
def conformance():
    """
    OGC API conformance endpoint

    :returns: HTTP response
    """

    return get_response(api_.conformance(request))


@BLUEPRINT.route('/TileMatrixSets/<tileMatrixSetId>')
def get_tilematrix_set(tileMatrixSetId=None):
    """
    OGC API TileMatrixSet endpoint

    :param tileMatrixSetId: identifier of tile matrix set

    :returns: HTTP response
    """

    return execute_from_flask(tiles_api.tilematrixset, request,
                              tileMatrixSetId)


@BLUEPRINT.route('/TileMatrixSets')
def get_tilematrix_sets():
    """
    OGC API TileMatrixSets endpoint

    :returns: HTTP response
    """

    return execute_from_flask(tiles_api.tilematrixsets, request)


@BLUEPRINT.route('/collections')
@BLUEPRINT.route('/collections/<path:collection_id>')
def collections(collection_id=None):
    """
    OGC API collections endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """

    return get_response(api_.describe_collections(request, collection_id))


@BLUEPRINT.route('/collections/<path:collection_id>/schema')
def collection_schema(collection_id):
    """
    OGC API - collections schema endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """

    return get_response(api_.get_collection_schema(request, collection_id))


@BLUEPRINT.route('/collections/<path:collection_id>/queryables')
def collection_queryables(collection_id=None):
    """
    OGC API collections queryables endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """

    return execute_from_flask(itemtypes_api.get_collection_queryables, request,
                              collection_id)


@BLUEPRINT.route('/collections/<path:collection_id>/items',
                 methods=['GET', 'POST', 'OPTIONS'],
                 provide_automatic_options=False)
@BLUEPRINT.route('/collections/<path:collection_id>/items/<path:item_id>',
                 methods=['GET', 'PUT', 'DELETE', 'OPTIONS'],
                 provide_automatic_options=False)
def collection_items(collection_id, item_id=None):
    """
    OGC API collections items endpoint

    :param collection_id: collection identifier
    :param item_id: item identifier

    :returns: HTTP response
    """

    if item_id is None:
        if request.method == 'GET':  # list items
            return execute_from_flask(itemtypes_api.get_collection_items,
                                      request, collection_id,
                                      skip_valid_check=True)
        elif request.method == 'POST':  # filter or manage items
            if request.content_type is not None:
                if request.content_type == 'application/geo+json':
                    return execute_from_flask(
                            itemtypes_api.manage_collection_item,
                            request, 'create', collection_id,
                            skip_valid_check=True)
                else:
                    return execute_from_flask(
                            itemtypes_api.post_collection_items, request,
                            collection_id, skip_valid_check=True)
        elif request.method == 'OPTIONS':
            return execute_from_flask(
                    itemtypes_api.manage_collection_item, request, 'options',
                    collection_id, skip_valid_check=True)

    elif request.method == 'DELETE':
        return execute_from_flask(itemtypes_api.manage_collection_item,
                                  request, 'delete', collection_id, item_id,
                                  skip_valid_check=True)
    elif request.method == 'PUT':
        return execute_from_flask(itemtypes_api.manage_collection_item,
                                  request, 'update', collection_id, item_id,
                                  skip_valid_check=True)
    elif request.method == 'OPTIONS':
        return execute_from_flask(itemtypes_api.manage_collection_item,
                                  request, 'options', collection_id, item_id,
                                  skip_valid_check=True)
    else:
        return execute_from_flask(itemtypes_api.get_collection_item, request,
                                  collection_id, item_id)


@BLUEPRINT.route('/collections/<path:collection_id>/coverage')
def collection_coverage(collection_id):
    """
    OGC API - Coverages coverage endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """

    return execute_from_flask(coverages_api.get_collection_coverage, request,
                              collection_id, skip_valid_check=True)


@BLUEPRINT.route('/collections/<path:collection_id>/tiles')
def get_collection_tiles(collection_id=None):
    """
    OGC open api collections tiles access point

    :param collection_id: collection identifier

    :returns: HTTP response
    """

    return execute_from_flask(tiles_api.get_collection_tiles, request,
                              collection_id)


@BLUEPRINT.route('/collections/<path:collection_id>/tiles/<tileMatrixSetId>')
@BLUEPRINT.route('/collections/<path:collection_id>/tiles/<tileMatrixSetId>/metadata')  # noqa
def get_collection_tiles_metadata(collection_id=None, tileMatrixSetId=None):
    """
    OGC open api collection tiles service metadata

    :param collection_id: collection identifier
    :param tileMatrixSetId: identifier of tile matrix set

    :returns: HTTP response
    """

    return execute_from_flask(tiles_api.get_collection_tiles_metadata,
                              request, collection_id, tileMatrixSetId,
                              skip_valid_check=True)


@BLUEPRINT.route('/collections/<path:collection_id>/tiles/\
<tileMatrixSetId>/<tileMatrix>/<tileRow>/<tileCol>')
def get_collection_tiles_data(collection_id=None, tileMatrixSetId=None,
                              tileMatrix=None, tileRow=None, tileCol=None):
    """
    OGC open api collection tiles service data

    :param collection_id: collection identifier
    :param tileMatrixSetId: identifier of tile matrix set
    :param tileMatrix: identifier of {z} matrix index
    :param tileRow: identifier of {y} matrix index
    :param tileCol: identifier of {x} matrix index

    :returns: HTTP response
    """

    return execute_from_flask(
        tiles_api.get_collection_tiles_data,
        request, collection_id, tileMatrixSetId, tileMatrix, tileRow, tileCol,
        skip_valid_check=True,
    )


@BLUEPRINT.route('/collections/<collection_id>/map')
@BLUEPRINT.route('/collections/<collection_id>/styles/<style_id>/map')
def collection_map(collection_id, style_id=None):
    """
    OGC API - Maps map render endpoint

    :param collection_id: collection identifier
    :param style_id: style identifier

    :returns: HTTP response
    """

    return execute_from_flask(
        maps_api.get_collection_map, request, collection_id, style_id
    )


@BLUEPRINT.route('/processes')
@BLUEPRINT.route('/processes/<process_id>')
def get_processes(process_id=None):
    """
    OGC API - Processes description endpoint

    :param process_id: process identifier

    :returns: HTTP response
    """

    return execute_from_flask(processes_api.describe_processes, request,
                              process_id)


@BLUEPRINT.route('/jobs')
@BLUEPRINT.route('/jobs/<job_id>',
                 methods=['GET', 'DELETE'])
def get_jobs(job_id=None):
    """
    OGC API - Processes jobs endpoint

    :param job_id: job identifier

    :returns: HTTP response
    """

    if job_id is None:
        return execute_from_flask(processes_api.get_jobs, request)
    else:
        if request.method == 'DELETE':  # dismiss job
            return execute_from_flask(processes_api.delete_job, request,
                                      job_id)
        else:  # Return status of a specific job
            return execute_from_flask(processes_api.get_jobs, request, job_id)


@BLUEPRINT.route('/processes/<process_id>/execution', methods=['POST'])
def execute_process_jobs(process_id):
    """
    OGC API - Processes execution endpoint

    :param process_id: process identifier

    :returns: HTTP response
    """

    return execute_from_flask(processes_api.execute_process, request,
                              process_id)


@BLUEPRINT.route('/jobs/<job_id>/results',
                 methods=['GET'])
def get_job_result(job_id=None):
    """
    OGC API - Processes job result endpoint

    :param job_id: job identifier

    :returns: HTTP response
    """

    return execute_from_flask(processes_api.get_job_result, request, job_id)


@BLUEPRINT.route('/jobs/<job_id>/results/<resource>',
                 methods=['GET'])
def get_job_result_resource(job_id, resource):
    """
    OGC API - Processes job result resource endpoint

    :param job_id: job identifier
    :param resource: job resource

    :returns: HTTP response
    """

    # TODO: this does not seem to exist?
    return get_response(api_.get_job_result_resource(
        request, job_id, resource))


@BLUEPRINT.route('/collections/<path:collection_id>/position')
@BLUEPRINT.route('/collections/<path:collection_id>/area')
@BLUEPRINT.route('/collections/<path:collection_id>/cube')
@BLUEPRINT.route('/collections/<path:collection_id>/radius')
@BLUEPRINT.route('/collections/<path:collection_id>/trajectory')
@BLUEPRINT.route('/collections/<path:collection_id>/corridor')
@BLUEPRINT.route('/collections/<path:collection_id>/locations/<location_id>')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/locations')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/position')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/area')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/cube')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/radius')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/trajectory')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/corridor')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/locations/<location_id>')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/locations')  # noqa
def get_collection_edr_query(collection_id, instance_id=None,
                             location_id=None):
    """
    OGC EDR API endpoints

    :param collection_id: collection identifier
    :param instance_id: instance identifier
    :param location_id: location id of a /locations/<location_id> query

    :returns: HTTP response
    """

    if location_id:
        query_type = 'locations'
    else:
        query_type = request.path.split('/')[-1]

    return execute_from_flask(
        edr_api.get_collection_edr_query, request, collection_id, instance_id,
        query_type, location_id,
        skip_valid_check=True,
    )


@BLUEPRINT.route('/stac')
def stac_catalog_root():
    """
    STAC root endpoint

    :returns: HTTP response
    """

    return execute_from_flask(stac_api.get_stac_root, request)


@BLUEPRINT.route('/stac/<path:path>')
def stac_catalog_path(path):
    """
    STAC path endpoint

    :param path: path

    :returns: HTTP response
    """

    return execute_from_flask(stac_api.get_stac_path, request, path)


@ADMIN_BLUEPRINT.route('/admin/config', methods=['GET', 'PUT', 'PATCH'])
def admin_config():
    """
    Admin endpoint

    :returns: HTTP response
    """

    if request.method == 'GET':
        return get_response(admin_.get_config(request))

    elif request.method == 'PUT':
        return get_response(admin_.put_config(request))

    elif request.method == 'PATCH':
        return get_response(admin_.patch_config(request))


@ADMIN_BLUEPRINT.route('/admin/config/resources', methods=['GET', 'POST'])
def admin_config_resources():
    """
    Resources endpoint

    :returns: HTTP response
    """

    if request.method == 'GET':
        return get_response(admin_.get_resources(request))

    elif request.method == 'POST':
        return get_response(admin_.post_resource(request))


@ADMIN_BLUEPRINT.route(
    '/admin/config/resources/<resource_id>',
    methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def admin_config_resource(resource_id):
    """
    Resource endpoint

    :returns: HTTP response
    """

    if request.method == 'GET':
        return get_response(admin_.get_resource(request, resource_id))

    elif request.method == 'DELETE':
        return get_response(admin_.delete_resource(request, resource_id))

    elif request.method == 'PUT':
        return get_response(admin_.put_resource(request, resource_id))

    elif request.method == 'PATCH':
        return get_response(admin_.patch_resource(request, resource_id))


APP.register_blueprint(BLUEPRINT)

if CONFIG['server'].get('admin'):
    admin_ = Admin(CONFIG, OPENAPI)
    APP.register_blueprint(ADMIN_BLUEPRINT)


@click.command()
@click.pass_context
@click.option('--debug', '-d', default=False, is_flag=True, help='debug')
def serve(ctx, server=None, debug=False):
    """
    Serve pygeoapi via Flask. Runs pygeoapi
    as a flask server. Not recommend for production.

    :param server: `string` of server type
    :param debug: `bool` of whether to run in debug mode

    :returns: void
    """

    # setup_logger(CONFIG['logging'])
    APP.run(debug=True, host=api_.config['server']['bind']['host'],
            port=api_.config['server']['bind']['port'])


if __name__ == '__main__':  # run locally, for testing
    serve()
