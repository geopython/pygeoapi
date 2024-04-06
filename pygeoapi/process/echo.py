# =================================================================
#
# Authors: Alexander Pilz <a.pilz@52north.org>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2023 Alexander Pilz
# Copyright (c) 2023 Tom Kralidis
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
import time

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

LOGGER = logging.getLogger(__name__)

#: Process metadata and description
PROCESS_METADATA = {
  'id': 'echo',
  'title': 'Echo Process',
  'description': 'Testable Echo process.',
  'version': '1.0.0',
  'jobControlOptions': [
    'async-execute',
    'sync-execute'
  ],
  'outputTransmission': [
    'value',
    'reference'
  ],
  'inputs': {
    'echoInput': {
      'title': 'Echo value',
      'description': 'Value to be echoed back.',
      'minOccurs': 1,
      'maxOccurs': 1,
      'schema': {
        'type': 'string',
        'enum': [
          'Echo',
          'Test',
          '42'
        ]
      }},
    'pause': {
      'title': 'Pause value',
      'description': 'Value to control the processing time.',
      'minOccurs': 1,
      'maxOccurs': 1,
      'schema': {
        'type': 'number',
        'enum': [
          5.5,
          10.25,
          42.0
        ]
      }
    }
  },
  'outputs': {
    'echoOutput': {
      'schema': {
        'type': 'string'
      }
    }
  },
  'links': [{
        'type': 'text/html',
        'rel': 'about',
        'title': 'information',
        'href': 'https://example.org/process',
        'hreflang': 'en-US'
    }],
  'example': {
    'inputs': {
      'echo': 'echoValue',
      'pause': 10.0
      }
  }
}


class EchoProcessor(BaseProcessor):
    """Echo Processor example"""
    def __init__(self, processor_def):
        """
        Initialize object

        :param processor_def: provider definition

        :returns: pygeoapi.process.echo.EchoProcessor
        """

        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data):

        mimetype = 'application/json'

        echo = data.get('echoInput')
        pause = data.get('pause')

        if echo is None:
            raise ProcessorExecuteError(
                'Cannot run process without echo value')

        if not isinstance(echo, str):
            raise ProcessorExecuteError(
                'Cannot run process with echo not of type string')

        outputs = {
            'id': 'echoOutput',
            'value': echo
        }

        if pause is not None and isinstance(pause, float):
            time.sleep(pause)

        return mimetype, outputs

    def __repr__(self):
        return f'<EchoProcessor> {self.name}'
