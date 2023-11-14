# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Norman Barker <norman.barker@gmail.com>
#
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

"""Flask module providing the route paths to the api"""

from http import HTTPStatus
from pathlib import Path

from flask import (
    current_app,
    Blueprint,
    Flask,
    make_response,
    request,
    send_from_directory
)

from pygeoapi.api import API
import pygeoapi.util


BLUEPRINT = Blueprint('pygeoapi', __name__)


def get_response(result: tuple):
    """
    Creates a Flask Response object and updates matching headers.

    :param result: The result of the API call.
                   This should be a tuple of (headers, status, content).

    :returns: A Response instance.
    """

    headers, status, content = result
    response = make_response(content, status)

    if headers:
        response.headers = headers
    return response


@BLUEPRINT.route('/schemas/<path:path>', methods=['GET'])
def schemas(path):
    """Serve OGC schemas locally

    :param path: path of the OGC schema document

    :returns: HTTP response
    """

    api_: API = current_app.config['PYGEOAPI']['api']
    ogc_schemas_location = api_.config.get(
        'server', {}).get('ogc_schemas_location')
    got_local_schemas = not ogc_schemas_location.startswith('http')
    if ogc_schemas_location is not None:
        if got_local_schemas:
            schemas_dir = Path(ogc_schemas_location).resolve()
            if schemas_dir.is_dir():
                return send_from_directory(
                    schemas_dir,
                    schemas_dir.name,
                    mimetype=pygeoapi.util.get_mimetype(schemas_dir.name)
                )
            else:
                raise RuntimeError('OGC schemas misconfigured')
        else:
            return (
                (
                    "OGC SCHEMAS are configured as a remote resource - "
                    "cannot serve locally"
                ),
                HTTPStatus.NOT_FOUND
            )
    else:
        return (
            "OGC SCHEMAS are not configured - cannot serve locally",
            HTTPStatus.NOT_FOUND
        )


@BLUEPRINT.route('/')
def landing_page():
    """
    OGC API landing page endpoint

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.landing_page(request))


@BLUEPRINT.route('/openapi')
def openapi():
    """
    OpenAPI endpoint

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.openapi_(request))


@BLUEPRINT.route('/conformance')
def conformance():
    """
    OGC API conformance endpoint

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.conformance(request))


@BLUEPRINT.route('/collections')
@BLUEPRINT.route('/collections/<path:collection_id>')
def collections(collection_id=None):
    """
    OGC API collections endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.describe_collections(request, collection_id))


@BLUEPRINT.route('/collections/<path:collection_id>/queryables')
def collection_queryables(collection_id=None):
    """
    OGC API collections querybles endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.get_collection_queryables(request, collection_id))


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

    api_: API = current_app.config['PYGEOAPI']['api']
    if item_id is None:
        if request.method == 'GET':  # list items
            return get_response(
                api_.get_collection_items(request, collection_id))
        elif request.method == 'POST':  # filter or manage items
            if request.content_type is not None:
                if request.content_type == 'application/geo+json':
                    return get_response(
                        api_.manage_collection_item(request, 'create',
                                                    collection_id))
                else:
                    return get_response(
                        api_.post_collection_items(request, collection_id))
        elif request.method == 'OPTIONS':
            return get_response(
                api_.manage_collection_item(request, 'options', collection_id))

    elif request.method == 'DELETE':
        return get_response(
            api_.manage_collection_item(request, 'delete',
                                        collection_id, item_id))
    elif request.method == 'PUT':
        return get_response(
            api_.manage_collection_item(request, 'update',
                                        collection_id, item_id))
    elif request.method == 'OPTIONS':
        return get_response(
            api_.manage_collection_item(request, 'options',
                                        collection_id, item_id))
    else:
        return get_response(
            api_.get_collection_item(request, collection_id, item_id))


@BLUEPRINT.route('/collections/<path:collection_id>/coverage')
def collection_coverage(collection_id):
    """
    OGC API - Coverages coverage endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.get_collection_coverage(request, collection_id))


@BLUEPRINT.route('/collections/<path:collection_id>/coverage/domainset')
def collection_coverage_domainset(collection_id):
    """
    OGC API - Coverages coverage domainset endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.get_collection_coverage_domainset(
        request, collection_id))


@BLUEPRINT.route('/collections/<path:collection_id>/coverage/rangetype')
def collection_coverage_rangetype(collection_id):
    """
    OGC API - Coverages coverage rangetype endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.get_collection_coverage_rangetype(
        request, collection_id))


@BLUEPRINT.route('/collections/<path:collection_id>/tiles')
def get_collection_tiles(collection_id=None):
    """
    OGC open api collections tiles access point

    :param collection_id: collection identifier

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.get_collection_tiles(
        request, collection_id))


@BLUEPRINT.route('/collections/<path:collection_id>/tiles/<tileMatrixSetId>')
@BLUEPRINT.route('/collections/<path:collection_id>/tiles/<tileMatrixSetId>/metadata')  # noqa
def get_collection_tiles_metadata(collection_id=None, tileMatrixSetId=None):
    """
    OGC open api collection tiles service metadata

    :param collection_id: collection identifier
    :param tileMatrixSetId: identifier of tile matrix set

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.get_collection_tiles_metadata(
        request, collection_id, tileMatrixSetId))


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
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.get_collection_tiles_data(
        request, collection_id, tileMatrixSetId, tileMatrix, tileRow, tileCol))


@BLUEPRINT.route('/collections/<collection_id>/map')
@BLUEPRINT.route('/collections/<collection_id>/styles/<style_id>/map')
def collection_map(collection_id, style_id=None):
    """
    OGC API - Maps map render endpoint

    :param collection_id: collection identifier
    :param style_id: style identifier

    :returns: HTTP response
    """

    api_: API = current_app.config['PYGEOAPI']['api']
    headers, status_code, content = api_.get_collection_map(
        request, collection_id, style_id)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@BLUEPRINT.route('/processes')
@BLUEPRINT.route('/processes/<process_id>')
def get_processes(process_id=None):
    """
    OGC API - Processes description endpoint

    :param process_id: process identifier

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.describe_processes(request, process_id))


@BLUEPRINT.route('/jobs')
@BLUEPRINT.route('/jobs/<job_id>',
                 methods=['GET', 'DELETE'])
def get_jobs(job_id=None):
    """
    OGC API - Processes jobs endpoint

    :param job_id: job identifier

    :returns: HTTP response
    """

    api_: API = current_app.config['PYGEOAPI']['api']
    if job_id is None:
        return get_response(api_.get_jobs(request))
    else:
        if request.method == 'DELETE':  # dismiss job
            return get_response(api_.delete_job(request, job_id))
        else:  # Return status of a specific job
            return get_response(api_.get_jobs(request, job_id))


@BLUEPRINT.route('/processes/<process_id>/execution', methods=['POST'])
def execute_process_jobs(process_id):
    """
    OGC API - Processes execution endpoint

    :param process_id: process identifier

    :returns: HTTP response
    """

    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.execute_process(request, process_id))


@BLUEPRINT.route('/jobs/<job_id>/results',
                 methods=['GET'])
def get_job_result(job_id=None):
    """
    OGC API - Processes job result endpoint

    :param job_id: job identifier

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.get_job_result(request, job_id))


@BLUEPRINT.route('/jobs/<job_id>/results/<resource>',
                 methods=['GET'])
def get_job_result_resource(job_id, resource):
    """
    OGC API - Processes job result resource endpoint

    :param job_id: job identifier
    :param resource: job resource

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.get_job_result_resource(
        request, job_id, resource))


@BLUEPRINT.route('/collections/<path:collection_id>/position')
@BLUEPRINT.route('/collections/<path:collection_id>/area')
@BLUEPRINT.route('/collections/<path:collection_id>/cube')
@BLUEPRINT.route('/collections/<path:collection_id>/radius')
@BLUEPRINT.route('/collections/<path:collection_id>/trajectory')
@BLUEPRINT.route('/collections/<path:collection_id>/corridor')
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/position')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/area')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/cube')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/radius')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/trajectory')  # noqa
@BLUEPRINT.route('/collections/<path:collection_id>/instances/<instance_id>/corridor')  # noqa
def get_collection_edr_query(collection_id, instance_id=None):
    """
    OGC EDR API endpoints

    :param collection_id: collection identifier
    :param instance_id: instance identifier

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    query_type = request.path.split('/')[-1]
    return get_response(api_.get_collection_edr_query(request, collection_id,
                                                      instance_id, query_type))


@BLUEPRINT.route('/stac')
def stac_catalog_root():
    """
    STAC root endpoint

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.get_stac_root(request))


@BLUEPRINT.route('/stac/<path:path>')
def stac_catalog_path(path):
    """
    STAC path endpoint

    :param path: path

    :returns: HTTP response
    """
    api_: API = current_app.config['PYGEOAPI']['api']
    return get_response(api_.get_stac_path(request, path))


def create_app(pygeoapi_config_path: str, pygeoapi_openapi_path: str) -> Flask:
    """Create the pygeoapi flask application"""
    pygeoapi_config = pygeoapi.util.get_config_from_path(
        Path(pygeoapi_config_path))
    pygeoapi_openapi_document = pygeoapi.util.get_openapi_from_path(
        Path(pygeoapi_openapi_path))
    api = API(config=pygeoapi_config, openapi=pygeoapi_openapi_document)
    static_folder = (
        pygeoapi_config.get('server', {})
        .get('templates', {})
        .get('static', 'static')
    )
    app = Flask(
        __name__,
        static_folder=static_folder,
        static_url_path='/static'
    )
    api_rules = pygeoapi.util.get_api_rules(pygeoapi_config)
    app.url_map.strict_slashes = api_rules.strict_slashes
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = pygeoapi_config.get(
        'server', {}).get('pretty_print', True)
    app.config['PYGEOAPI'] = {
        'api': api,
    }
    if pygeoapi_config.get('server', {}).get('cors', False):
        try:
            from flask_cors import CORS
            CORS(app)
        except ModuleNotFoundError:
            print('Python package flask-cors required for CORS support')

    app.register_blueprint(BLUEPRINT)
    return app
