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

from paho.mqtt import client as mqtt_client

from pygeoapi.pubsub.base import BasePubSubClient, PubSubClientConnectionError

LOGGER = logging.getLogger(__name__)


class MQTTPubSubClient(BasePubSubClient):
    """MQTT client"""

    def __init__(self, broker_url):
        """
        Initialize object

        :param publisher_def: provider definition

        :returns: pycsw.pubsub.mqtt.MQTTPubSubClient
        """

        super().__init__(broker_url)
        self.type = 'mqtt'
        self.port = self.broker_url.port

        self.userdata = {}

        msg = f'Connecting to broker {self.broker_safe_url} with id {self.client_id}'  # noqa
        LOGGER.debug(msg)
        self.conn = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2,
                                       client_id=self.client_id)

        self.conn.enable_logger(logger=LOGGER)

        if None not in [self.broker_url.username, self.broker_url.password]:
            LOGGER.debug('Setting credentials')
            self.conn.username_pw_set(
                self.broker_url.username,
                self.broker_url.password)

        if self.port is None:
            if self.broker_url.scheme == 'mqtts':
                self.port = 8883
            else:
                self.port = 1883

        if self.broker_url.scheme == 'mqtts':
            self.conn.tls_set(tls_version=2)

    def connect(self) -> None:
        """
        Connect to an MQTT broker

        :returns: None
        """

        try:
            self.conn.connect(self.broker_url.hostname, self.port)
            LOGGER.debug('Connected to broker')
        except Exception as err:
            raise PubSubClientConnectionError(err)

    def pub(self, channel: str, message: str, qos: int = 1) -> bool:
        """
        Publish a message to a broker/channel

        :param channel: `str` of channel
        :param message: `str` of message

        :returns: `bool` of publish result
        """

        LOGGER.debug(f'Publishing to broker {self.broker_safe_url}')
        LOGGER.debug(f'Channel: {channel}')
        LOGGER.debug(f'Message: {message}')

        result = self.conn.publish(channel, message, qos)
        LOGGER.debug(f'Result: {result}')

        # TODO: investigate implication
        # result.wait_for_publish()

        if result.is_published:
            LOGGER.debug('Message published')
            return True
        else:
            msg = f'Publishing error code: {result[1]}'
            LOGGER.warning(msg)
            return False

    def __repr__(self):
        return f'<MQTTPubSubClient> {self.broker_safe_url}'
