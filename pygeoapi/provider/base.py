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

from urllib.request import urlparse


class BaseProvider(object):
    """generic Provider ABC"""

    def __init__(self, definition):
        """initializer"""

        self.type = definition['type']
        self.id_field = definition['id_field']

        parsed_url = urlparse(definition['url'])

        if parsed_url.scheme == 'file':
            self.url = parsed_url.path
        else:
            self.url = definition['url']

    def query(self):
        """
        query the provider

        :returns: dict of 0..n GeoJSON features
        """

        raise NotImplementedError()

    def get(self, identifier):
        """
        query the provider by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """

        raise NotImplementedError()

    def __repr__(self):
        return '<BaseProvider> {}'.format(self.type)
