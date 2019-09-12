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

"""Generic util functions used in the code"""

import logging

import yaml

LOGGER = logging.getLogger(__name__)


def get_url(scheme, host, port, basepath):
    """
    Provides URL of instance

    :returns: string of complete baseurl
    """

    url = '{}://{}'.format(scheme, host)

    if port not in [80, 443]:
        url = '{}:{}'.format(url, port)

    url = '{}{}'.format(url, basepath)

    return url


def yaml_load(fh):
    """
    serializes a YAML files into a pyyaml object

    :param fh: file handle

    :returns: `dict` representation of YAML
    """

    try:
        return yaml.load(fh, Loader=yaml.FullLoader)
    except AttributeError as err:
        LOGGER.warning('YAML loading error: {}'.format(err))
        return yaml.load(fh)


def str2bool(value):
    """
    helper function to return Python boolean
    type (source: https://stackoverflow.com/a/715468)

    :param value: value to be evaluated

    :returns: `bool` of whether the value is boolean-ish
    """

    value2 = False

    if isinstance(value, bool):
        value2 = value
    else:
        value2 = value.lower() in ('yes', 'true', 't', '1', 'on')

    return value2
