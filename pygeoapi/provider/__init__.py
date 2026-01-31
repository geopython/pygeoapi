# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2026 Tom Kralidis
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

from pygeoapi.provider.base import ProviderTypeError

LOGGER = logging.getLogger(__name__)


def filter_providers_by_type(providers: list, type: str) -> dict:
    """
    helper function to filter a list of providers by type

    :param providers: ``list``
    :param type: str

    :returns: filtered ``dict`` provider
    """

    providers_ = {provider['type']: provider for provider in providers}
    return providers_.get(type)


def get_provider_by_type(providers: list, provider_type: str) -> dict:
    """
    helper function to load a provider by a provider type

    :param providers: ``list`` of providers
    :param provider_type: type of provider (e.g. feature)

    :returns: provider based on type
    """

    LOGGER.debug(f'Searching for provider type {provider_type}')
    try:
        p = (next(d for i, d in enumerate(providers)
                  if d['type'] == provider_type))
    except (RuntimeError, StopIteration):
        raise ProviderTypeError('Invalid provider type requested')

    return p


def get_provider_default(providers: list) -> dict:
    """
    helper function to get a resource's default provider

    :param providers: ``list`` of providers

    :returns: filtered ``dict``
    """

    try:
        default = (next(d for i, d in enumerate(providers) if 'default' in d
                   and d['default']))
        LOGGER.debug('found default provider type')
    except StopIteration:
        LOGGER.debug('no default provider type.  Returning first provider')
        default = providers[0]

    LOGGER.debug(f"Default provider: {default['type']}")
    return default
