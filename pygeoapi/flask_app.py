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
from pygeoapi.util import get_mimetype, yaml_load, filter_dict_by_key_value

import re


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
def landing_page():
    """
    OGC API landing page endpoint

    :returns: HTTP response
    """
    headers, status_code, content = api_.landing_page(
        request.headers, request.args)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@APP.route('/openapi')
def openapi():
    """
    OpenAPI endpoint

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
    OGC API conformance endpoint

    :returns: HTTP response
    """

    headers, status_code, content = api_.conformance(request.headers,
                                                     request.args)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@APP.route('/collections')
@APP.route('/collections/<collection_id>')
def collections(collection_id=None):
    """
    OGC API collections endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """

    headers, status_code, content = api_.describe_collections(
        request.headers, request.args, collection_id)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@APP.route('/collections/<collection_id>/queryables')
def collection_queryables(collection_id=None):
    """
    OGC API collections querybles endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """

    headers, status_code, content = api_.get_collection_queryables(
        request.headers, request.args, collection_id)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


def supports_transactions(collection):
    """
    Check if given collection supports transactions

    :param collection: collection dict

    :returns: boolean value
    """

    if 'extensions' not in CONFIG['resources'][collection]:
        return False
    if 'transactions' not in CONFIG['resources'][collection]['extensions']:
        return False
    return CONFIG['resources'][collection]['extensions']['transactions']


def dataset(item_id=None):
    """
    OGC API collections items endpoint

    :param collection_id: collection identifier
    :param item_id: item identifier

    :returns: HTTP response
    """
    # -------- find collection id from request object -------------
    path = request.path
    coll_id_pattern = re.compile("/collections/(.*)/items")
    collection_id = coll_id_pattern.findall(path)[0]
    # -------------------------------------------------------------

    verb = request.method

    if verb == 'GET':
        if item_id is None:
            headers, status_code, content = api_.get_collection_items(
                request.headers, request.args, collection_id)
        else:
            headers, status_code, content = api_.get_collection_item(
                request.headers, request.args, collection_id, item_id)

    req_body = request.get_json()

    if verb == 'POST':
        headers, status_code, content = api_.create_collection_item(
                req_body, collection_id)

    if verb == 'PUT':
        headers, status_code, content = api_.replace_collection_item(
                req_body, collection_id, item_id)

    if verb == 'PATCH':
        headers, status_code, content = api_.update_collection_item(
                req_body, collection_id, item_id)

    if verb == 'DELETE':
        headers, status_code, content = api_.remove_collection_item(
                collection_id, item_id)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


# ------------ dynamic routing based on transactions flag --------------
coll = filter_dict_by_key_value(CONFIG['resources'],
                                'type', 'collection')
coll_support_trans = list(filter(supports_transactions, coll))
# route get for both paths of every collection
for collection_id in coll:
    APP.add_url_rule('/collections/'+collection_id+'/items',
                     'dataset', dataset,
                     methods=['GET'])
    APP.add_url_rule('/collections/'+collection_id+'/items/<item_id>',
                     'dataset', dataset,
                     methods=['GET'])
# route transaction verbs selectively for each path and each collection
for collection_id in coll_support_trans:
    APP.add_url_rule('/collections/'+collection_id+'/items',
                     'dataset', dataset,
                     methods=['POST'])
    APP.add_url_rule('/collections/'+collection_id+'/items/<item_id>',
                     'dataset', dataset,
                     methods=['PATCH', 'PUT', 'DELETE'])
# ------------------------------------------------------------------------


@APP.route('/processes')
@APP.route('/processes/<process_id>')
def processes(process_id=None):
    '''
    OGC API - Processes jobs endpoint

    :param process_id: process identifier

    :returns: HTTP response
    '''
    headers, status_code, content = api_.describe_processes(
        request.headers, request.args, process_id)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@APP.route('/processes/<process_id>/jobs', methods=['GET', 'POST'])
def process_jobs(process_id=None):
    """
    OGC API - Processes jobs endpoint

    :param process_id: process identifier

    :returns: HTTP response
    """

    if request.method == 'GET':
        headers, status_code, content = ({}, 200, "[]")
    elif request.method == 'POST':
        headers, status_code, content = api_.execute_process(
            request.headers, request.args, request.data, process_id)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@APP.route('/stac')
def stac_catalog_root():
    """
    STAC root endpoint

    :returns: HTTP response
    """

    headers, status_code, content = api_.get_stac_root(
        request.headers, request.args)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@APP.route('/stac/<path:path>')
def stac_catalog_path(path):
    """
    STAC path endpoint

    :param path: path

    :returns: HTTP response
    """

    headers, status_code, content = api_.get_stac_path(
        request.headers, request.args, path)

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

    :returns: void
    """

#    setup_logger(CONFIG['logging'])
    APP.run(debug=True, host=api_.config['server']['bind']['host'],
            port=api_.config['server']['bind']['port'])


if __name__ == '__main__':  # run locally, for testing
    serve()
