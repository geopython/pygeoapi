
import logging
from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError
LOGGER = logging.getLogger(__name__)
# TODO Improve logging!

import argparse
import subprocess
import geojson
import os
import sys
import tempfile


'''

Written by Merret on 2023-10-06 - 2023-10-11
Just for testing purposes - licenses not checked yet!

It does the same as snap_to_network.R,
see https://github.com/glowabio/hydrographr/blob/HEAD/R/snap_to_network.R
Which calls:
https://github.com/glowabio/hydrographr/blob/a818de3e9165d108034fd342c2a85e0a3c7ec7ca/inst/sh/snap_to_network.sh
Done to to understand what that one is doing exactly!

Documentation:
https://glowabio.github.io/hydrographr/reference/snap_to_network.html

How to call this service?
curl -X POST "http://localhost:5000/processes/snap-to-network/execution" -H "Content-Type: application/json" -d "{\"inputs\":{\"method\": \"distance\", \"accumulation\": 0.5, \"distance\": 500, \"coordinate_multipoint\":{\"coordinates\": [[-17.25355, -44.885825], [-13.763611, -43.595833]], \"type\": \"MultiPoint\"}}}" 

How to add this service to an existing pygeoapi instance?
* Add to plugins.py
* Add to pygeoapi-config.yml
* Add code into directory process (bash scripts need to be executable!)
* Install any python dependencies into the pygeoapo virtualenv!

Locally, the data dir is:
export PYGEOAPI_DATA_DIR="/home/mbuurman/work/testing_hydrographr/data/basin_481051"

'''



#: Process metadata and description
PROCESS_METADATA = {
    'version': '0.0.1',
    'id': 'snap-to-network',
    'title': {'en': 'Snap to network'},
    'description': {
        'en': 'Trying to expose snap_to_network from hydrographr package as ogc process: '
              'https://glowabio.github.io/hydrographr/reference/snap_to_network.html.'
    },
    'jobControlOptions': ['sync-execute', 'async-execute'],
    'keywords': ['hydrographr', 'example', 'echo'],
    'links': [{
        'type': 'text/html',
        'rel': 'about',
        'title': 'information',
        'href': 'https://example.org/process',
        'hreflang': 'en-US'
    }],
    'inputs': {
        'coordinate_multipoint': {
            'title': 'Coordinate Multipoint',
            'description': 'Dunno exactly.',
            'schema': {
                'type': 'object',
                'contentMediaType': 'application/json'
            },
            'minOccurs': 1,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
            'keywords': ['coordinates']
        },
        'method': {
            'title': 'Method',
            'description': '"distance", "accumulation", or "both". Defines if the points are snapped using the distance or flow accumulation.',
            'schema': {'type': 'string'},
            'minOccurs': 1,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
            'keywords': ['snapping']
        },
        'distance': {
            'title': 'Distance',
            'description': 'Maximum radius in map pixels. The points will be snapped to the next stream within this radius.',
            'schema': {'type': 'string'},
            'minOccurs': 1,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
            'keywords': ['bla']
        },
        'accumulation': {
            'title': 'Accumulation',
            'description': 'Minimum flow accumulation. Points will be snapped to the next stream with a flow accumulation equal or higher than the given value.',
            'schema': {'type': 'string'},
            'minOccurs': 1,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
            'keywords': ['bla']
        }
    },
    'outputs': {
        'snapped_points': {
            'title': 'Snapped Points',
            'description': 'Resulting coordinates as multipoint.',
            'schema': {
                'type': 'object',
                'contentMediaType': 'application/json'
            }
        }
    },
    'example': {
        'inputs': {
            'coordinate_multipoint': "{\"coordinates\": [[-17.25355, -44.885825], [-13.763611, -43.595833]], \"type\": \"MultiPoint\"}"
        }
    }
}

class SnapToNetworkProcessor(BaseProcessor):
    """Get Snap-to-Network Processor example"""

    def __init__(self, processor_def):
        """
        Initialize object

        :param processor_def: provider definition

        :returns: pygeoapi.process.get_tide_id.SnapToNetworkProcessor
        """

        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data):
        LOGGER.info('Starting "snap_to_network as ogc_service!"')

        # Get PYGEOAPI_DATA_DIR from environment:
        if not 'PYGEOAPI_DATA_DIR' in os.environ:
            print('ERROR: Missing environment variable PYGEOAPI_DATA_DIR. We cannot find the input data!\nPlease run:\nexport PYGEOAPI_DATA_DIR="/.../"')
            print('Exiting...')
            sys.exit(1) # This leads to curl error: (52) Empty reply from server. TODO: Send error message back!!!

        # Get input:
        method = data.get('method')
        distance = data.get('distance')
        accumulation = data.get('accumulation')

        # Check validity of argument:
        if not method in ['distance', 'accumulation', 'both']:
            LOGGER.error('Error: Wrong method: %s' % method)

        # Already in geoJSON I think, no need to run geojson.loads()
        multipoint = data.get('coordinate_multipoint')
        LOGGER.debug('Input multipoint: %s (%s)' % (multipoint, type(multipoint)))

        # Make a file out of the input geojson, as the bash file wants them as a file
        # Otherwise, rewrite the bash file to python!
        input_coord_file_path =  tempfile.gettempdir()+os.sep+'__input_snappingtool.txt'
        col_name_lat = 'lat'
        col_name_lon = 'lon'
        col_name_id = 'dummy_unused' # or so! I don't think is is really used, is it? TODO check this third column business
        self.make_file_from_geojson(multipoint, input_coord_file_path, col_name_lat, col_name_lon)

        # Hardcoded paths on server:
        # TODO: Do we have to cut them smaller for processing?
        #path_accumul_tif = '/home/mbuurman/work/testing_hydrographr/data/basin_481051/accumulation_481051.tif'
        #path_stream_tif  = '/home/mbuurman/work/testing_hydrographr/data/basin_481051/segment_481051.tif'
        # TODO The file name is still hardcoded!
        path_accumul_tif = os.environ['PYGEOAPI_DATA_DIR']+os.sep+'accumulation_481051.tif'
        path_stream_tif  = os.environ['PYGEOAPI_DATA_DIR']+os.sep+'segment_481051.tif'
        tmp_dir =  tempfile.gettempdir()
        snap_tmp_path =  tempfile.gettempdir()+os.sep+'__output_snappingtool.txt' # intermediate result storage used by GRASS!

        # Now call the tool:
        snap_tmp_path = self.call_snap_to_network_sh(input_coord_file_path,
            col_name_id, col_name_lon, col_name_lat,
            path_stream_tif, path_accumul_tif,
            method, distance, accumulation,
            snap_tmp_path, tmp_dir)

        # Now make geojson from the tool:
        result_multipoint = self.csv_to_geojson(snap_tmp_path)
        LOGGER.debug('________________________________')
        LOGGER.info('Result multipoint: %s' % result_multipoint)
        #LOGGER.info('Result multipoint: %s (dumped)' % geosjon.dumps(result_multipoint))

        outputs = {
            'id': 'snapped_points',
            'value': result_multipoint
        }

        mimetype = 'application/json'
        return mimetype, outputs

    def __repr__(self):
        return f'<SnapToNetworkProcessor> {self.name}'


    def make_file_from_geojson(self, multipoint, input_coord_file_path, col_name_lat='lat', col_name_lon='lon', sep=','):

        LOGGER.debug('Writing input coordinates from geojson into "%s"...' % input_coord_file_path)
        with open(input_coord_file_path, 'w') as inputfile: # Overwrite previous input file!
            inputfile.write('%s%s%s%s%s\n' % ("foo", sep, col_name_lon, sep, col_name_lat))
            for coord_pair in multipoint['coordinates']:
                lon = coord_pair[0]
                lat = coord_pair[1]
                coord_pair_str = '%s%s%s%s%s\n' % (99999, sep, lat, sep, lon) # comma separated
                inputfile.write(coord_pair_str)

        # DEBUG TODO FIXME This is a dirty little fix
        # This is what happens in R in this line:
        # https://github.com/glowabio/hydrographr/blob/HEAD/R/snap_to_network.R#L193C3-L193C17
        # They just export the coordinates, no other columns!
        # But the input line in grass seems to expect more lines!
        # Line 73 in snap_to_network.sh:
        # https://github.com/glowabio/hydrographr/blob/24e350f1606e60a02594b4d655501ca68bc3e846/inst/sh/snap_to_network.sh#L73
        # So I now added another dummy foo column in front.

        return input_coord_file_path


    def call_snap_to_network_sh(self, path_coord_file, id_col_name, lon_col_name, lat_col_name, path_stream_tif, path_accumul_tif, method, distance, accumulation, snap_tmp_path, tmp_dir):
        
        with open(snap_tmp_path, 'w') as myfile:
            pass # To empty the file! #- can be done more elegant I'm sure!

        LOGGER.debug('Now calling bash which calls grass/gdal...')
        LOGGER.debug('Current directory: %s' % os.getcwd())
        bash_file = os.getcwd()+'/pygeoapi/process/snap_to_network.sh'
        cmd =[bash_file, path_coord_file, id_col_name, lon_col_name, lat_col_name,
              path_stream_tif, path_accumul_tif, method, str(distance), str(accumulation), snap_tmp_path, tmp_dir]
        LOGGER.debug('GRASS command: %s' % cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        stdoutdata, stderrdata = p.communicate()
        LOGGER.debug('Process exit code: %s' % p.returncode)
        LOGGER.debug('Process output:\n____________\n%s\n_____(end of process stdout)_______' % stdoutdata.decode())
        if len(stderrdata.decode()) > 0:
            LOGGER.debug('Process errors:\n____________\n%s\n_____(end of process stderr)_______' % stderrdata.decode())
        else:
            LOGGER.debug('(Nothing written to stderr: "%s")' % stderrdata.decode())
        return snap_tmp_path


    def csv_to_geojson(self, snap_tmp_path):
        # Get results by reading them from result file!
        # This is how GeoJSON Multipoints look:
        # "{\"coordinates\": [[-17.25355, -44.885825], [-13.763611, -43.595833]], \"type\": \"MultiPoint\"}"
        result_multipoint = {"type": "MultiPoint", "coordinates":[]}
        LOGGER.debug('Reading snapped points from GRASS result file "%s" and writing them into a GeoJSON Multipoint...' % snap_tmp_path)
        firstline = True
        with open(snap_tmp_path, 'r') as resultfile:
            for line in resultfile:

                # Ignore header line!
                if firstline:
                    firstline = False
                    continue

                line = line.strip()
                LOGGER.debug('Found coordinate line: %s' % line) # TODO Understand why we get so many columns here!
                splitted = line.split()

                # Which columns?
                coord1, coord2 = splitted[1], splitted[2]
                LOGGER.debug('Extracted these coordinates %s, %s' % (coord1, coord2))
                result_multipoint['coordinates'].append([coord2, coord1])
        LOGGER.debug('Finished creating GeoJSON multipoint: %s' % geojson.dumps(result_multipoint))
        return result_multipoint
