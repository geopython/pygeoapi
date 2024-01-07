# =================================================================
#
# Authors: Krishna Lodha <krishna@rottengrapes.com>
#
# Copyright (c) 2023 Krishna Lodha
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

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError
import shapely 

LOGGER = logging.getLogger(__name__)

#: Process metadata and description
PROCESS_METADATA = {
    'version': '0.2.0',
    'id': 'geom-contains',
    'title': {
        'en': 'Shapely Contains functon',
        'fr': 'Shapely Contains functon'
    },
    'description': {
        'en': 'An example process that takes 2 geometries (A & B) in WKT Format '
              'and returns Boolean representing if B is completely withing A',
        'fr': 'Un exemple de processus qui prend 2 géométries (A et B) au format WKT '
              '''et renvoie une valeur booléenne représentant si B est complètement à l'intérieur de A'''
    },
    'jobControlOptions': ['sync-execute', 'async-execute'],
    'keywords': ['contains', 'shapely', ],
    'links': [{
        'type': 'text/html',
        'rel': 'about',
        'title': 'information',
        'href': 'https://example.org/process',
        'hreflang': 'en-US'
    }],
    'inputs': {
        'A': {
            'title': 'Geometry A',
            'description': 'Bigger Geometry in which Geometry A should be',
            'schema': {
                'type': 'string'
            },
            'minOccurs': 1,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
            'keywords': ['Geometry A',]
        },
        'B': {
            'title': 'Geometry B',
            'description': 'Smaller Geometry which will be tested against Geometry A',
            'schema': {
                'type': 'string'
            },
            'minOccurs': 1,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
            'keywords': ['Geometry A',]
        },
    },
    'outputs': {
        'result': {
            'Contains': True,
            
        }
    },
    'example': {
        'inputs': {
            'A': 'POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))',
            'B': 'POINT (5 5)',
        }
    }
}


class ContainsProcessor(BaseProcessor):
    """Shapely Contain Processor example"""

    def __init__(self, processor_def):
        """
        Initialize object

        :param processor_def: provider definition

        :returns: pygeoapi.process.shapely_functions.ContainsProcessor
        """

        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data):

        mimetype = 'application/json'
        geomA = data.get('A')
        geomB = data.get('B')

        if geomA is None or geomB is None:
            raise ProcessorExecuteError('Cannot process without both geometries')

        try :
            geometryA = shapely.wkt.loads(geomA)
            geometryB = shapely.wkt.loads(geomB)
        except:
            raise ProcessorExecuteError('Geometries WKT format is incorrect')
        if geometryA.contains(geometryB):
            contain = True
        else :
            contain = False

        outputs = {
            'id': 'result',
            'Contains': contain
        }
        return mimetype, outputs

    def __repr__(self):
        return f'<ContainsProcessor> {self.name}'
