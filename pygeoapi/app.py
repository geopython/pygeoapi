# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
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
from urllib.parse import urlparse

from flask import (abort, Flask, jsonify, make_response,
                   render_template, request)
from flask_cors import CORS

import yaml

from pygeoapi import __version__
from pygeoapi import views

app = Flask(__name__)

with open(os.environ.get('PYGEOAPI_CONFIG')) as ff:
    config = yaml.load(ff)

path = urlparse(config['server']['url']).path

app.config['APPLICATION_ROOT'] = path

if not config['server']['pretty_print']:
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

if config['server']['cors']:
    CORS(app)


def get_exception(status, code, description):
    exception = {
        'code': code,
        'description': description
    }
    return make_response(jsonify(exception), status)


@app.errorhandler(404)
def not_found(error):
    return get_exception(404, 'NotFound', 'Not found')


@app.errorhandler(400)
def bad_request(error):
    return get_exception(400, 'BadRequest', 'Bad request')


@app.route('/api')
def api_json():
    """returns Swagger def"""

    return jsonify({'version': __version__})


@app.route('/api.html')
def api_html():
    """returns Swagger def as HTML"""

    return jsonify({'version': __version__})


@app.route('/api/conformance')
def api_conformance_json():
    """returns API conformance"""

    response = views.get_api_conformance_json()

    return make_response(jsonify(response))


@app.route('/')
def index_json():
    """returns Feature Collection Metadata JSON"""

    response = views.get_feature_collection_metadata(config)

    return make_response(jsonify(response))


@app.route('/index.html')
def index_html():
    return render_template('service.html', config=config, version=__version__)


@app.route('/<feature_collection>/')
@app.route('/<feature_collection>/<feature>')
def dataset(feature_collection, feature=None):
    """get feature from a feature collection"""

    startindex = 0
    count = 10
    resulttype = 'results'

    if 'startIndex' in request.args:
        startindex = int(request.args.get('startIndex'))
    if 'count' in request.args:
        count = int(request.args.get('count'))
    if 'resultType' in request.args:
        resulttype = request.args.get('resultType')

    if feature is None:
        response = views.get_feature_collection(config, feature_collection,
                                                startindex, count, resulttype)
    else:
        response = views.get_feature(config, feature_collection, feature)

    if response is None:
        abort(404)

    return make_response(jsonify(response))


if __name__ == '__main__':
    app.run(debug=True)
