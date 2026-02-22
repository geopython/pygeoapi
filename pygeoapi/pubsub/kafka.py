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

from kafka import errors, KafkaProducer

from pygeoapi.pubsub.base import BasePubSubClient, PubSubClientConnectionError
from pygeoapi.util import to_json

LOGGER = logging.getLogger(__name__)


class KafkaPubSubClient(BasePubSubClient):
    """Kafka client"""

    def __init__(self, publisher_def):
        """
        Initialize object

        :param publisher_def: provider definition

        :returns: pygeoapi.pubsub.kafka.KafkaPubSubClient
        """

        super().__init__(publisher_def)
        self.name = 'Kafka'
        self.type = 'kafka'
        self.sasl_mechanism = publisher_def.get('sasl.mechanism', 'PLAIN')
        self.security_protocol = publisher_def.get('security.protocol', 'SASL_SSL')  # noqa

        msg = f'Initializing to broker {self.broker_safe_url} with id {self.client_id}'  # noqa
        LOGGER.debug(msg)

    def connect(self) -> None:
        """
        Connect to an Kafka broker

        :returns: None
        """

        args = {
            'bootstrap_servers': f'{self.broker_url.hostname}:{self.broker_url.port}',  # noqa
            'client_id': self.client_id,
            'value_serializer': lambda v: to_json(v).encode('utf-8')
        }
        if None not in [self.broker_url.username, self.broker_url.password]:
            args.update({
                'security.protocol': self.security_protocol,
                'sasl.mechanism': self.sasl_mechanism,
                'sasl.username': self.broker_url.username,
                'sasl.password': self.broker_url.password
            })

        LOGGER.debug('Creating Kafka producer')
        try:
            self.producer = KafkaProducer(**args)
        except errors.NoBrokersAvailable as err:
            raise PubSubClientConnectionError(err)

    def pub(self, channel: str, message: str) -> bool:
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
        LOGGER.debug(f'Sanitized channel for Kafka: {channel}')

        self.producer.send(channel, value=message)
        self.producer.flush()

    def __repr__(self):
        return f'<HTTPPubSubClient> {self.broker_safe_url}'
