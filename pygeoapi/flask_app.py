# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Norman Barker <norman.barker@gmail.com>
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

""" Flask module providing the route paths to the api"""

import os

import click

from flask import Flask, Blueprint, make_response, request, send_from_directory

from pygeoapi.api import API
from pygeoapi.util import get_mimetype, yaml_load


CONFIG = None

if 'PYGEOAPI_CONFIG' not in os.environ:
    raise RuntimeError('PYGEOAPI_CONFIG environment variable not set')

with open(os.environ.get('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
    CONFIG = yaml_load(fh)

STATIC_FOLDER = 'static'
if 'templates' in CONFIG['server']:
    STATIC_FOLDER = CONFIG['server']['templates'].get('static', 'static')

APP = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path='/static')
APP.url_map.strict_slashes = False

BLUEPRINT = Blueprint('pygeoapi', __name__, static_folder=STATIC_FOLDER)

# CORS: optionally enable from config.
if CONFIG['server'].get('cors', False):
    from flask_cors import CORS
    CORS(APP)

APP.config['JSONIFY_PRETTYPRINT_REGULAR'] = CONFIG['server'].get(
    'pretty_print', True)

api_ = API(CONFIG)

OGC_SCHEMAS_LOCATION = CONFIG['server'].get('ogc_schemas_location', None)

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

        # TODO: better sanitization?
        path_ = dirname_.replace('..', '').replace('//', '')
        return send_from_directory(path_, basename_,
                                   mimetype=get_mimetype(basename_))


def get_response(result: tuple):
    """ Creates a Flask Response object and updates matching headers.

    :param result:  The result of the API call.
                    This should be a tuple of (headers, status, content).
    :returns:       A Response instance.
    """
    headers, status, content = result
    response = make_response(content, status)
    if headers:
        response.headers = headers
    return response


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
    with open(os.environ.get('PYGEOAPI_OPENAPI'), encoding='utf8') as ff:
        if os.environ.get('PYGEOAPI_OPENAPI').endswith(('.yaml', '.yml')):
            openapi_ = yaml_load(ff)
        else:  # JSON file, do not transform
            openapi_ = ff

    return get_response(api_.openapi(request, openapi_))


@BLUEPRINT.route('/conformance')
def conformance():
    """
    OGC API conformance endpoint

    :returns: HTTP response
    """
    return get_response(api_.conformance(request))


@BLUEPRINT.route('/collections')
@BLUEPRINT.route('/collections/<collection_id>')
def collections(collection_id=None):
    """
    OGC API collections endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """
    return get_response(api_.describe_collections(request, collection_id))


@BLUEPRINT.route('/collections/<collection_id>/queryables')
def collection_queryables(collection_id=None):
    """
    OGC API collections querybles endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """
    return get_response(api_.get_collection_queryables(request, collection_id))


@BLUEPRINT.route('/collections/<collection_id>/items')
@BLUEPRINT.route('/collections/<collection_id>/items/<item_id>')
def collection_items(collection_id, item_id=None):
    """
    OGC API collections items endpoint

    :param collection_id: collection identifier
    :param item_id: item identifier

    :returns: HTTP response
    """
    if item_id is None:
        return get_response(api_.get_collection_items(request, collection_id))
    return get_response(
        api_.get_collection_item(request, collection_id, item_id))


@BLUEPRINT.route('/collections/<collection_id>/coverage')
def collection_coverage(collection_id):
    """
    OGC API - Coverages coverage endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """
    return get_response(api_.get_collection_coverage(request, collection_id))


@BLUEPRINT.route('/collections/<collection_id>/coverage/domainset')
def collection_coverage_domainset(collection_id):
    """
    OGC API - Coverages coverage domainset endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """
    return get_response(api_.get_collection_coverage_domainset(
        request, collection_id))


@BLUEPRINT.route('/collections/<collection_id>/coverage/rangetype')
def collection_coverage_rangetype(collection_id):
    """
    OGC API - Coverages coverage rangetype endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """
    return get_response(api_.get_collection_coverage_rangetype(
        request, collection_id))


@BLUEPRINT.route('/collections/<collection_id>/tiles')
def get_collection_tiles(collection_id=None):
    """
    OGC open api collections tiles access point

    :param collection_id: collection identifier

    :returns: HTTP response
    """
    return get_response(api_.get_collection_tiles(
        request, collection_id))


@BLUEPRINT.route('/collections/<collection_id>/tiles/<tileMatrixSetId>/metadata')  # noqa
def get_collection_tiles_metadata(collection_id=None, tileMatrixSetId=None):
    """
    OGC open api collection tiles service metadata

    :param collection_id: collection identifier
    :param tileMatrixSetId: identifier of tile matrix set

    :returns: HTTP response
    """
    return get_response(api_.get_collection_tiles_metadata(
        request, collection_id, tileMatrixSetId))


@BLUEPRINT.route('/collections/<collection_id>/tiles/\
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
    return get_response(api_.get_collection_tiles_data(
        request, collection_id, tileMatrixSetId, tileMatrix, tileRow, tileCol))


@BLUEPRINT.route('/processes')
@BLUEPRINT.route('/processes/<process_id>')
def get_processes(process_id=None):
    """
    OGC API - Processes description endpoint

    :param process_id: process identifier

    :returns: HTTP response
    """
    return get_response(api_.describe_processes(request, process_id))


@BLUEPRINT.route('/processes/<process_id>/jobs', methods=['GET', 'POST'])
@BLUEPRINT.route('/processes/<process_id>/jobs/<job_id>',
                 methods=['GET', 'DELETE'])
def get_process_jobs(process_id=None, job_id=None):
    """
    OGC API - Processes jobs endpoint

    :param process_id: process identifier
    :param job_id: job identifier

    :returns: HTTP response
    """
    if job_id is None:
        if request.method == 'GET':  # list jobs
            return get_response(api_.get_process_jobs(request, process_id))
        elif request.method == 'POST':  # submit job
            return get_response(api_.execute_process(request, process_id))
    else:
        if request.method == 'DELETE':  # dismiss job
            return get_response(api_.delete_process_job(process_id, job_id))
        else:  # Return status of a specific job
            return get_response(api_.get_process_jobs(
                request, process_id, job_id))


@BLUEPRINT.route('/processes/<process_id>/jobs/<job_id>/results',
                 methods=['GET'])
def get_process_job_result(process_id=None, job_id=None):
    """
    OGC API - Processes job result endpoint

    :param process_id: process identifier
    :param job_id: job identifier

    :returns: HTTP response
    """
    return get_response(api_.get_process_job_result(
        request, process_id, job_id))


@BLUEPRINT.route('/processes/<process_id>/jobs/<job_id>/results/<resource>',
                 methods=['GET'])
def get_process_job_result_resource(process_id, job_id, resource):
    """
    OGC API - Processes job result resource endpoint

    :param process_id: process identifier
    :param job_id: job identifier
    :param resource: job resource

    :returns: HTTP response
    """
    return get_response(api_.get_process_job_result_resource(
        request, process_id, job_id, resource))


@BLUEPRINT.route('/collections/<collection_id>/position')
@BLUEPRINT.route('/collections/<collection_id>/area')
@BLUEPRINT.route('/collections/<collection_id>/cube')
@BLUEPRINT.route('/collections/<collection_id>/trajectory')
@BLUEPRINT.route('/collections/<collection_id>/corridor')
@BLUEPRINT.route('/collections/<collection_id>/instances/<instance_id>/position')  # noqa
@BLUEPRINT.route('/collections/<collection_id>/instances/<instance_id>/area')
@BLUEPRINT.route('/collections/<collection_id>/instances/<instance_id>/cube')
@BLUEPRINT.route('/collections/<collection_id>/instances/<instance_id>/trajectory')  # noqa
@BLUEPRINT.route('/collections/<collection_id>/instances/<instance_id>/corridor')  # noqa
def get_collection_edr_query(collection_id, instance_id=None):
    """
    OGC EDR API endpoints

    :param collection_id: collection identifier
    :param instance_id: instance identifier

    :returns: HTTP response
    """
    query_type = request.path.split('/')[-1]
    return get_response(api_.get_collection_edr_query(request, collection_id,
                                                      instance_id, query_type))


@BLUEPRINT.route('/stac')
def stac_catalog_root():
    """
    STAC root endpoint

    :returns: HTTP response
    """
    return get_response(api_.get_stac_root(request))


@BLUEPRINT.route('/stac/<path:path>')
def stac_catalog_path(path):
    """
    STAC path endpoint

    :param path: path

    :returns: HTTP response
    """
    return get_response(api_.get_stac_path(request, path))


APP.register_blueprint(BLUEPRINT)


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
