# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2019 Tom Kralidis
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

from pygeoapi.process.base import BaseProcessor

LOGGER = logging.getLogger(__name__)

#: Process metadata and description
PROCESS_METADATA = {
    'version': '0.2.0',
    'id': 'hello-world',
    'title': 'Hello World',
    'description': 'An example processes that takes a name as input, and echoes it back as output. Intended to demonstrate a simple process with a single literal input.',
    'keywords': ['hello world', 'example', 'echo'],
    'links': [{
        'type': 'text/html',
        'rel': 'canonical',
        'title': 'information',
        'href': 'https://example.org/process',
        'hreflang': 'en-US'
    }],
    'inputs': [{
        'id': 'name', # TODO a URI?
        'title': 'Name',
        'abstract': 'The name of the person or entity that you wish to be echoed back as an output.',
        'input': {
            'literalDataDomain': {
                'dataType': 'string',
                'valueDefinition': {
                    'anyValue': True
                }
            }
        },
        'minOccurs': 1,
        'maxOccurs': 1,
        'metadata': None, # TODO how to use?
        'keywords': ['full name', 'personal']
    }, {
        'id': 'message',
        'title': 'Message',
        'abstract': 'An optional message to echo as well.',
        'input': {
            'literalDataDomain': {
                'dataType': 'string',
                'valueDefinition': {
                    'anyValue': True
                }
            }
        },
        'minOccurs': 0,
        'maxOccurs': 1,
        'metadata': None,
        'keywords': ['message']
    }],
    'outputs': [{
        'id': 'echo',
        'title': 'A hello world echo with the name and (optional) message submitted for processing.',
        'output': {
            'formats': [{
                'mimeType': 'application/json'
            }]
        }
    }],
    'example': {
        'inputs': [{
            'id': 'name',
            'value': 'Ciarán',
            'type': 'text/plain'
        }]
    }
}


class HelloWorldProcessor(BaseProcessor):
    """Hello World Processor example"""

    def __init__(self, provider_def):
        """
        Initialize object
        :param provider_def: provider definition
        :returns: pygeoapi.process.hello_world.HelloWorldProcessor
        """

        BaseProcessor.__init__(self, provider_def, PROCESS_METADATA)

    def execute(self, data):
        name = data.get('name')
        if not name:
            raise Exception('Cannot process without a name')
        value = 'Hello {}! {}'.format(data['name'], data.get('message', '')).strip()
        outputs = [{
            'id': 'echo',
            'value': value
        }]

        return outputs

    def __repr__(self):
        return '<HelloWorldProcessor> {}'.format(self.name)
