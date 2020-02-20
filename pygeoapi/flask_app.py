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

from flask import Flask, make_response, request, send_from_directory

from pygeoapi.api import API
from pygeoapi.util import get_mimetype, yaml_load

APP = Flask(__name__)
APP.url_map.strict_slashes = False

CONFIG = None

if 'PYGEOAPI_CONFIG' not in os.environ:
    raise RuntimeError('PYGEOAPI_CONFIG environment variable not set')

with open(os.environ.get('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
    CONFIG = yaml_load(fh)

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

    @APP.route('/schemas/<path:path>', methods=['GET'])
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


@APP.route('/')
def root():
    """
    HTTP root content of pygeoapi. Intro page access point

    :returns: HTTP response
    """
    headers, status_code, content = api_.root(request.headers, request.args)

    response = make_response(content, status_code)
    if headers:
        response.headers = headers

    return response


@APP.route('/openapi')
def openapi():
    """
    OpenAPI access point

    :returns: HTTP response
    """
    with open(os.environ.get('PYGEOAPI_OPENAPI'), encoding='utf8') as ff:
        openapi = yaml_load(ff)

    headers, status_code, content = api_.openapi(request.headers, request.args,
                                                 openapi)

    response = make_response(content, status_code)
    if headers:
        response.headers = headers

    return response


@APP.route('/conformance')
def conformance():
    """
    OGC open api conformance access point

    :returns: HTTP response
    """

    headers, status_code, content = api_.conformance(request.headers,
                                                     request.args)

    response = make_response(content, status_code)
    if headers:
        response.headers = headers

    return response


@APP.route('/collections')
@APP.route('/collections/<name>')
def describe_collections(name=None):
    """
    OGC open api collections  access point

    :param name: identifier of collection name
    :returns: HTTP response
    """

    headers, status_code, content = api_.describe_collections(
        request.headers, request.args, name)

    response = make_response(content, status_code)
    if headers:
        response.headers = headers

    return response


@APP.route('/collections/<feature_collection>/items')
@APP.route('/collections/<feature_collection>/items/<feature>')
def dataset(feature_collection, feature=None):
    """
    OGC open api collections/{dataset}/items/{feature}  access point

    :returns: HTTP response
    """

    if feature is None:
        headers, status_code, content = api_.get_collection_items(
            request.headers, request.args, feature_collection)
    else:
        headers, status_code, content = api_.get_collection_item(
            request.headers, request.args, feature_collection, feature)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@APP.route('/processes', methods=['GET'])
@APP.route('/processes/<name>', methods=['GET'])
def describe_processes(name=None):
    """
    OGC WPS REST server respource to retrieve a process collection, or a process
    description. (Experimental.)

    :param name: identifier of process to describe; if None, retrieves the
        collection of processes
    :returns: HTTP response
    """
    headers, status_code, content = api_.describe_processes(
        request.headers, request.args, name)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@APP.route('/processes/<name>/jobs', methods=['GET', 'POST'])
@APP.route('/processes/<name>/jobs/<job_id>', methods=['GET'])
def execute_process(name=None, job_id=None):
    """
    OGC WPS REST server resource to obtain information about jobs submitted
    as instances of a particular process. If a particular job_id is submitted,
    returns additional information about that particular job. (Experimental.)
    :param name: identifier of process to execute
    :param job_id: unique server-generated ID of job
    :returns: HTTP response
    """
    if not job_id:
        # Request a new job (POST)
        # Get array of all job IDs (GET)
        headers, status_code, content = api_.execute_process(
            request.method, request.headers, request.args, request.data, name)
    else:
        # Return status of a specific job
        headers, status_code, content = api_.retrieve_job_status(
            request.headers, request.args, request.data, name, job_id
        )

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response

@APP.route('/processes/<name>/jobs/<job_id>/results', methods=['GET'])
def retrieve_job_result(name=None, job_id=None):
    """
    OGC EPS REST server resource to obtain the results of a particualar job (an
    instance of a process). Under synchronous execution, these results would
    have been returned to the client already (but can be requested again). Under
    asyncronous execution, this is the endpoint a client hits to obtain their
    results, via a Location header. (Experimental.)
    :param name: identifier of process to inspect
    :param job_id: unique ID of particular job executed under this process
    :returns: HTTP response
    """
    headers, status_code, content = api_.retrieve_job_result(
        request.method, request.headers, request.args, request.data, name, job_id
    )

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response

@click.command()
@click.pass_context
@click.option('--debug', '-d', default=False, is_flag=True, help='debug')
def serve(ctx, server=None, debug=False):
    """
    Serve pygeoapi via Flask. Runs pygeoapi
    as a flask server. Not recommend for production.

    :param server: `string` of server type
    :param debug: `bool` of whether to run in debug mode
    :returns void

    """

#    setup_logger(CONFIG['logging'])
    APP.run(debug=True, host=api_.config['server']['bind']['host'],
            port=api_.config['server']['bind']['port'])

if __name__ == '__main__':  # run locally, for testing
    serve()
