# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Angelos Tzotsos <tzotsos@gmail.com>
#
# Copyright (c) 2026 Tom Kralidis
# Copyright (c) 2025 Angelos Tzotsos
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

import requests

from pygeoapi.pubsub.base import BasePubSubClient, PubSubClientConnectionError

LOGGER = logging.getLogger(__name__)


class HTTPPubSubClient(BasePubSubClient):
    """HTTP client"""

    def __init__(self, publisher_def):
        """
        Initialize object

        :param publisher_def: provider definition

        :returns: pygeoapi.pubsub.http.HTTPPubSubClient
        """

        super().__init__(publisher_def)
        self.name = 'HTTP'
        self.type = 'http'
        self.auth = None

        msg = f'Initializing to broker {self.broker_safe_url} with id {self.client_id}'  # noqa
        LOGGER.debug(msg)

        if None not in [self.broker_url.username, self.broker_url.password]:
            LOGGER.debug('Setting credentials')
            self.auth = (
                self.broker_url.username,
                self.broker_url.password
            )

    def connect(self) -> None:
        """
        Connect to an HTTP broker

        :returns: None
        """

        LOGGER.debug('No connection to HTTP')
        pass

    def pub(self, channel: str, message: str, qos: int = 1) -> bool:
        """
        Publish a message to a broker/channel

        :param channel: `str` of topic
        :param message: `str` of message

        :returns: `bool` of publish result
        """

        LOGGER.debug(f'Publishing to broker {self.broker_safe_url}')
        LOGGER.debug(f'Channel: {channel}')
        LOGGER.debug(f'Message: {message}')
        LOGGER.debug('Sanitizing channel for HTTP')
        channel = channel.replace('/', '-')
        channel = channel.replace(':', '-')
        LOGGER.debug(f'Sanitized channel for HTTP: {channel}')

        url = f'{self.broker}/{channel}'

        try:
            response = requests.post(url, auth=self.auth, json=message)
            response.raise_for_status()
        except Exception as err:
            raise PubSubClientConnectionError(err)

    def __repr__(self):
        return f'<HTTPPubSubClient> {self.broker_safe_url}'
