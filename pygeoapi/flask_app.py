# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Norman Barker <norman.barker@gmail.com>
#
# Copyright (c) 2018 Tom Kralidis
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

import os

import click
import yaml

from flask import Flask, make_response, request

from pygeoapi.api import API

APP = Flask(__name__)
APP.url_map.strict_slashes = False

CONFIG = None

if 'PYGEOAPI_CONFIG' not in os.environ:
    raise RuntimeError('PYGEOAPI_CONFIG environment variable not set')

with open(os.environ.get('PYGEOAPI_CONFIG')) as fh:
    CONFIG = yaml.load(fh)

# CORS: optionally enable from config.
if CONFIG['server'].get('cors', False):
    from flask_cors import CORS
    CORS(APP)

APP.config['JSONIFY_PRETTYPRINT_REGULAR'] = \
    CONFIG['server'].get('pretty_print', True)

api_ = API(CONFIG)


@APP.route('/')
def root():
    headers, status_code, content = api_.root(request.headers, request.args)

    response = make_response(content, status_code)
    if headers:
        response.headers = headers

    return response


@APP.route('/api')
def api():
    with open(os.environ.get('PYGEOAPI_OPENAPI')) as ff:
        openapi = yaml.load(ff)

    headers, status_code, content = api_.api(request.headers, request.args,
                                             openapi)

    response = make_response(content, status_code)
    if headers:
        response.headers = headers

    return response


@APP.route('/conformance')
def api_conformance():
    headers, status_code, content = api_.api_conformance(request.headers,
                                                         request.args)

    response = make_response(content, status_code)
    if headers:
        response.headers = headers

    return response


@APP.route('/collections')
@APP.route('/collections/<name>')
def describe_collections(name=None):
    headers, status_code, content = api_.describe_collections(
        request.headers, request.args, name)

    response = make_response(content, status_code)
    if headers:
        response.headers = headers

    return response


@APP.route('/collections/<feature_collection>/items')
@APP.route('/collections/<feature_collection>/items/<feature>')
def dataset(feature_collection, feature=None):
    if feature is None:
        headers, status_code, content = api_.get_features(
            request.headers, request.args, feature_collection)
    else:
        headers, status_code, content = api_.get_feature(
            request.headers, request.args, feature_collection, feature)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@APP.route('/processes')
@APP.route('/processes/<name>')
def describe_processes(name=None):
    headers, status_code, content = api_.describe_processes(
        request.headers, request.args, name)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@APP.route('/processes/<name>/jobs', methods=['GET', 'POST'])
def execute_process(name=None):
    if request.method == 'GET':
        headers, status_code, content = ({}, 200, "[]")
    elif request.method == 'POST':
        headers, status_code, content = api_.execute_process(
            request.headers, request.args, request.data, name)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@click.command()
@click.pass_context
@click.option('--debug', '-d', default=False, is_flag=True, help='debug')
def serve(ctx, debug=False):
    """Serve pygeoapi via Flask"""

#    setup_logger(CONFIG['logging'])
    APP.run(debug=True, host=api_.config['server']['bind']['host'],
            port=api_.config['server']['bind']['port'])


if __name__ == '__main__':  # run locally, for testing
    serve()
