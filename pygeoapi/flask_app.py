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

import yaml
import click

from flask import Flask, make_response, request
from flask_cors import CORS

from pygeoapi import views
from pygeoapi.config import settings
from pygeoapi.log import setup_logger
from pygeoapi.util import get_url

APP = Flask(__name__)


@APP.route('/')
def root():
    headers, status_code, content = views.root(
        request.headers, request.args, APP.config['PYGEOAPI_BASEURL'])

    response = make_response(content, status_code)
    if headers:
        response.headers = headers

    return response


@APP.route('/api')
def api():
    with open(os.environ.get('PYGEOAPI_OPENAPI')) as ff:
        openapi = yaml.load(ff)

    headers, status_code, content = views.api(request.headers, request.args,
                                              openapi)

    response = make_response(content, status_code)
    if headers:
        response.headers = headers

    return response


@APP.route('/conformance')
def api_conformance():
    headers, status_code, content = views.api_conformance(request.headers,
                                                          request.args)

    response = make_response(content, status_code)
    if headers:
        response.headers = headers

    return response


@APP.route('/collections')
def describe_collections():
    headers, status_code, content = views.describe_collections(
        request.headers, request.args)

    response = make_response(content, status_code)
    if headers:
        response.headers = headers

    return response


@APP.route('/collections/<feature_collection>/')
@APP.route('/collections/<feature_collection>/<feature>')
def dataset(feature_collection, feature=None):
    if feature is None:
        headers, status_code, content = views.get_features(
            request.headers, request.args, feature_collection)
    else:
        headers, status_code, content = views.get_feature(
            request.headers, request.args, feature_collection, feature)

    response = make_response(content, status_code)

    if headers:
        response.headers = headers

    return response


@click.command()
@click.pass_context
@click.option('--debug', '-d', default=False, is_flag=True, help='debug')
def serve(ctx, debug=False):
    """Serve pygeoapi via Flask"""

    if not settings['server']['pretty_print']:
        APP.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

    if settings['server']['cors']:
        CORS(APP)

    setup_logger()
    # TODO: get scheme
    BASEURL = get_url('http', settings['server']['host'],
                      settings['server']['port'],
                      settings['server']['basepath'])
    APP.config['PYGEOAPI_BASEURL'] = BASEURL
    APP.run(debug=True)
