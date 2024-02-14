# =================================================================
#
# Authors: Ms. Prajwalita Jayadev Chavan <prajwalita.chavan@gmail.com>
#
# Copyright (c) 2024 Prajwalita Jayadev Chavan, GISE Hub, IIT Bombay
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

LOGGER = logging.getLogger(__name__)
# =================================================================

#: Process metadata and description
PROCESS_METADATA = {
    'version': '0.1.0',
    'id': 'shapely',
    'title': {
        'en': 'Shapely processor'
    },
    'description': {
        'en': 'An OGC API: processes that takes a polygon, line or point and find out buffer by using shapely.buffer '
              'the shapely buffer result'
    },
    'jobControlOptions': ['sync-execute', 'async-execute'],
    'keywords': ['shapely'],
    'links': [{
        'type': 'text/html',
        'rel': 'about',
        'title': 'information',
        'href': 'https://example.org/process',
        'hreflang': 'en-US'
    }],
    'inputs': {
        'number': {
            'title': 'Number',
            'description': 'number',
            'schema': {
                'oneOf': ['number', 'integer'],
            },
            'minOccurs': 1,
            'maxOccurs': 1,
            'metadata': None,  #  how to use?
            'keywords': ['number']
        }
    },
    'outputs': {
        'shapely': {
            'title': 'Shapely',
            'description': 'An example process that takes a number or '
                           'JSON file and returns the buffer result',
            'schema': {
                'type': 'object',
                'contentMediaType': 'application/geo+json'
            }
        }
    },
    'example': {
        'inputs': {
            #number

            #x, y, buffer

            #path of shape file
            
        }
    }
}
# =================================================================




class ShapelyProcessor(BaseProcessor):
    """Shapely Processor example"""

    def __init__(self, processor_def):
        """
        Initialize object

        :param processor_def: provider definition

        :returns: pygeoapi.process.shapely.ShapelyProcessor
        """

        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data):

        value = None
        mimetype = 'application/geo+json'
        
        #ShapelyBuffer for Point
        from shapely.geometry import Point

        p = Point(-75, 45)
        value = p.buffer(0.01).wkt

        outputs = {
            'id': 'shapely',
            'value': value
        }
        # =================================================================

        #ShapelyBuffer with user input line
        from shapely.geometry import Point

        number = data.get('number')    
        if number is None:
             raise ProcessorExecuteError('Cannot process without input')
        x, y= [float (c) for c in number.split()]       
        p = Point(x, y)
        value = p.buffer(0.01).wkt

        outputs = {
            'id': 'shapely',
            'value': value
        }
        # =================================================================


         #ShapelyBuffer for Point with user input buffer
        from shapely.geometry import Point

        x = float(data.get('x'))
        y = float(data.get('y'))
        buffer = int(data.get('buffer'))
        if x is None:
            raise ProcessorExecuteError('Cannot process without input x')
        if y is None:
            raise ProcessorExecuteError('Cannot process without input y')
        if buffer is None:
            raise ProcessorExecuteError('Cannot process without input buffer')         
        p = Point(x, y)
        value = p.buffer(buffer).wkt

        outputs = {
            'id': 'shapely',
            'value': value
        }
        # =================================================================


        #ShapelyBuffer for Polygon geometry (Triangle)
        from shapely.geometry import Polygon

        buffer = int(data.get('buffer'))        
        if buffer is None:
             raise ProcessorExecuteError('Cannot process without input buffer')
        
        polygon = Polygon([(0, 0), (1, 1), (1, 0)]) # Triangle
        value = polygon.buffer(buffer).wkt

        outputs = {
            'id': 'shapely',
            'value': value
        }
        # =================================================================


        #ShapelyBuffer for Polygon: read shape file and find buffer Pune
        import fiona
        from shapely.geometry import shape, LineString

        path = '/pygeoapi/mydata/Pune_OSM_Poly_Shape.shp' #polygon with only one feature
        c = fiona.open(path)
        collection = [ shape(item['geometry']) for item in c ]
        b = [ pol.buffer(0.01).wkt for pol in collection ]  
               
        outputs = {
            'id': 'shapely',
            'value': b[0]
        }
        # =================================================================


        #Read shape file with Line(water streams) and find buffer for Mandi Village, Himachal Pradesh
        import fiona
        import json       
        import shapely
        from shapely.wkt import loads
        from shapely import wkt                
        import geopandas as gpd
        from shapely.geometry import shape, LineString, Polygon, mapping
        from sys import argv
        from os.path import exists

        path = '/pygeoapi/mydata/Mandi_Village_Streams.shp' #polygon with only one feature
        c = fiona.open(path)
        collection = [ shape(item['geometry']) for item in c ]        
        rings = [ pol.buffer(0.0001) for pol in collection ] 
        ra= shapely.geometry.mapping(rings[0])             
        file = '/pygeoapi/mydata/xyfile.json'     
        output = open(file, 'w')
        json.dump(ra, output)             
                       
        outputs = ra   
        # =================================================================      
        
        
             
       
        #Final output
        return mimetype, outputs

    def __repr__(self):
        return f'<ShapelyProcessor> {self.name}'



