# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
# Authors: Benjamin Webb <benjamin.miller.webb@gmail.com>
#
# Copyright (c) 2023 Tom Kralidis
# Copyright (c) 2023 Benjamin Webb
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

import logging

from flask import Blueprint, request, make_response

from pygeoapi.admin import Admin
from pygeoapi.config import get_config

LOGGER = logging.getLogger(__name__)

CONFIG = get_config()

STATIC_FOLDER = 'static'
if 'templates' in CONFIG['server']:
    STATIC_FOLDER = CONFIG['server']['templates'].get('static', 'static')

admin_ = Admin(CONFIG)
ADMIN_BLUEPRINT = Blueprint('admin', __name__, static_folder=STATIC_FOLDER)


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


@ADMIN_BLUEPRINT.route('/admin')
def admin():
    """
    Admin landing page endpoint

    :returns: HTTP response
    """
    return get_response(admin_.admin(request))


@ADMIN_BLUEPRINT.route('/admin/resources', methods=['GET', 'POST'])
def resources():
    """
    Resource landing page endpoint

    :returns: HTTP response
    """
    if request.method == 'GET':
        return get_response(admin_.resources(request))

    elif request.method == 'POST':
        return get_response(admin_.post_resource(request))


@ADMIN_BLUEPRINT.route(
    '/admin/resources/<resource_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE']
)
def resource(resource_id):
    """
    Resource landing page endpoint

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
