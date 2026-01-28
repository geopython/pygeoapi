# =================================================================

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

from datetime import datetime, UTC
import json
import logging
import uuid
from typing import Union

LOGGER = logging.getLogger(__name__)

CONFORMANCE_CLASSES = [
    'https://www.opengis.net/spec/ogcapi-pubsub-1/1.0/conf/message-payload-cloudevents-json',  # noqa
    'https://www.opengis.net/spec/ogcapi-pubsub-1/1.0/conf/discovery'
]


def publish_message(pubsub_client, url: str, action: str,
                    resource: str = None, item: str = None,
                    data: dict = None) -> bool:
    """
    Publish broker message

    :param pubsub_client: `pygeoapi.pubsub.BasePubSubClient` instance
    :param url: `str` of server base URL
    :param action: `str` of action trigger name (create, update, delete)
    :param resource: `str` of resource identifier
    :param item: `str` of item identifier
    :param data: `dict` of data payload

    :returns: `bool` of whether message publishing was successful
    """

    if action in ['create', 'update']:
        channel = f'collections/{resource}'
        data_ = data
        media_type = 'application/geo+json'
        type_ = f'org.ogc.api.collection.item.{action}'
    elif action == 'delete':
        channel = f'collections/{resource}'
        data_ = item
        media_type = 'text/plain'
        type_ = f'org.ogc.api.collection.item.{action}'
    elif action == 'process':
        channel = f'processes/{resource}'
        media_type = 'application/json'
        data_ = data
        type_ = 'org.ogc.api.job.result'

    if pubsub_client.channel is not None:
        channel = f'{pubsub_client.channel}/{channel}'

    message = generate_ogc_cloudevent(type_, media_type, url,
                                      channel, data_)
    LOGGER.debug(f'Message: {message}')

    pubsub_client.connect()
    pubsub_client.pub(channel, json.dumps(message))


def generate_ogc_cloudevent(type_: str, media_type: str, source: str,
                            subject: str, data: Union[dict, str]) -> dict:
    """
    Generate CloudEvent

    :param type_: `str` of CloudEvents type
    :param source: `str` of source
    :param subject: `str` of subject
    :param media_type: `str` of media type
    :param data: `str` or `dict` of data

    :returns: `dict` of OGC CloudEvent payload
    """

    try:
        data2 = json.loads(data)
    except Exception:
        if isinstance(data, bytes):
            data2 = data.decode('utf-8')
        else:
            data2 = data

    message = {
        'specversion': '1.0',
        'type': type_,
        'source': source,
        'subject': subject,
        'id': str(uuid.uuid4()),
        'time': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'datacontenttype': media_type,
        # 'dataschema': 'TODO',
        'data': data2
    }

    return message


def get_oas_30(cfg, locale_):
    return [], {}
