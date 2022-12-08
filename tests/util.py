# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
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

import logging
import os.path

from werkzeug.test import create_environ
from werkzeug.wrappers import Request
from werkzeug.datastructures import ImmutableMultiDict

LOGGER = logging.getLogger(__name__)


def get_test_file_path(filename: str) -> str:
    """helper function to open test file safely"""

    if os.path.isfile(filename):
        return filename
    else:
        return 'tests/{}'.format(filename)


def mock_request(params: dict = None, data=None, **headers) -> Request:
    """
    Mocks a Request object so the @pre_process decorator can inject it
    as an APIRequest.

    :param params: Optional query parameter dict for the request.
                   Will be set to {} if omitted.
    :param data: Optional data/body to send with the request.
                 Can be text/bytes or a JSON dictionary.
    :param headers: Optional request HTTP headers to set.
    :returns: A Werkzeug Request instance.
    """
    params = params or {}
    # TODO: We are not setting a path in the create_environ() call.
    #       This is fine as long as an API test does not need the URL path.
    if isinstance(data, dict):
        environ = create_environ(base_url='http://localhost:5000/', json=data)
    else:
        environ = create_environ(base_url='http://localhost:5000/', data=data)
    environ.update(headers)
    request = Request(environ)
    request.args = ImmutableMultiDict(params.items())
    return request
