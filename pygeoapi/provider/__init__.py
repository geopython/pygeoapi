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

import importlib

PROVIDERS = {
    'Elasticsearch': 'pygeoapi.provider.elasticsearch.ElasticsearchProvider'
}


def load_provider(provider_obj):
    """
    loads provider by name

    :param name: name of provider

    :returns: provider object
    """

    provider_name = provider_obj['type']
    if provider_name not in PROVIDERS.keys():
        raise InvalidProviderError('provider not found')

    packagename, classname = PROVIDERS[provider_name].rsplit('.', 1)

    module = importlib.import_module(packagename)
    class_ = getattr(module, classname)
    provider = class_(provider_obj)
    return provider


class InvalidProviderError(Exception):
    """invalid provider"""

    pass
