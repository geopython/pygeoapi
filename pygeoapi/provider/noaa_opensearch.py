# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2024 Tom Kralidis
# Copyright (c) 2025 Francesco Bartoli
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

from opensearchpy import OpenSearch, RequestsHttpConnection

import requests
from requests_auth_aws_sigv4 import AWSSigV4

from pygeoapi.provider.base import ProviderConnectionError
from pygeoapi.provider.opensearch import OpenSearchProvider

LOGGER = logging.getLogger(__name__)


class NOAAOpenSearchProvider(OpenSearchProvider):
    """NOAA OpenSearch Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.opensearch_.OpenSearchProvider
        """

        self.select_properties = []

        self.os_host, self.index_name = self.data.rsplit('/', 1)
        self.aws_role = provider_def.get('aws_role')

        LOGGER.debug('Setting OpenSearch properties')

        LOGGER.debug(f'host: {self.os_host}')
        LOGGER.debug(f'index: {self.index_name}')
        LOGGER.debug(f'aws_role: {self.aws_role}')

        LOGGER.debug('Connecting to OpenSearch')
        self.os_ = OpenSearch(self.os_host, verify_certs=0)

        token_url = 'http://169.254.169.254/latest/api/token'
        token_headers = {'X-aws-ec2-metadata-token-ttl-seconds': '21600'}
        token = requests.put(token_url, headers=token_headers).text
        creds_headers = {'X-aws-ec2-metadata-token': token}
        creds_url = f'http://169.254.169.254/latest/meta-data/iam/security-credentials/{self.aws_role}'  # noqa
        creds_json = requests.get(creds_url, headers=creds_headers).json()

        aws_auth = AWSSigV4(
            'es',
            aws_access_key_id=creds_json['AccessKeyId'],
            aws_secret_access_key=creds_json['SecretAccessKey'],
            aws_session_token=creds_json['Token'],
            region='us-east-1')

        self.os_ = OpenSearch(hosts=self.os_host, http_auth=aws_auth,
                              use_ssl=True, verify_certs=True,
                              connection_class=RequestsHttpConnection)

        if not self.os_.ping():
            msg = f'Cannot connect to OpenSearch: {self.os_host}'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

        LOGGER.debug('Determining OpenSearch version')
        v = self.os_.info()['version']['number'][:3]
        LOGGER.debug(f'OpenSearch version: {v}')
      
