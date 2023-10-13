
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

Written by Merret on 2023-10-13
Just for testing purposes - licenses not checked yet!

curl -X POST "http://localhost:5000/processes/get-filtered-vector/execution" -H "Content-Type: application/json" -d "{\"inputs\":{\"basin_id\": 481051, \"attributes\": \"basin\"}}" 



'''



#: Process metadata and description
PROCESS_METADATA = {
    'version': '0.0.1',
    'id': 'get-filtered-vector',
    'title': {'en': 'Get filtered vector file'},
    'description': {
        'en': 'Trying to expose stuff from hydrographr package as ogc process: '
              'https://glowabio.github.io/hydrographr/'
    },
    'jobControlOptions': ['sync-execute', 'async-execute'],
    'keywords': ['hydrographr', 'example'],
    'links': [{
        'type': 'text/html',
        'rel': 'about',
        'title': 'information',
        'href': 'https://example.org/process',
        'hreflang': 'en-US'
    }],
    'inputs': {
        'basin_id': {
            'title': 'Basin Id',
            'description': 'The Id of the Basin',
            'schema': {'type': 'string'},
            'minOccurs': 1,
            'maxOccurs': 1,
            'metadata': None,  # TODO how to use?
            'keywords': ['river basin']
        },
        'attributes': {
            'title': 'Attributes',
            'description': 'Which attributes should be present in resulting vector file, e.g. "basin", "order_vect_segment".',
            'schema': {'type': 'string'}, # TODO: How to get a list of strings here?
            'minOccurs': 1,
            'maxOccurs': 1,
            'metadata': None,
            'keywords': ['vector attributes']
        }
    },
    'outputs': {
        'vector_file': {
            'title': 'Vector file',
            'description': 'Resulting vector file, as a file.',
            'schema': {
                'type': 'object',
                'contentMediaType': 'application/json' # TODO: How to send a file!
            }
        }
    },
    'example': {
        'inputs': {
            'basin_id': 481051,
            'attributes': 'basin'
        }
    }
}

class GetFilteredVector(BaseProcessor):
    """Get Get-Filtered-Vector Processor example"""

    def __init__(self, processor_def):
        """
        Initialize object

        :param processor_def: provider definition

        :returns: pygeoapi.process.get_tide_id.GetFilteredVector
        """

        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data):

        print('Starting "get_filtered_vector as ogc_service!"')
        print('bla1')

        # Get PYGEOAPI_DATA_DIR from environment:
        #if not 'PYGEOAPI_DATA_DIR' in os.environ:
        #    print('ERROR: Missing environment variable PYGEOAPI_DATA_DIR. We cannot find the input data!\nPlease run:\nexport PYGEOAPI_DATA_DIR="/.../"')
        #    print('Exiting...')
        #    sys.exit(1) # This leads to curl error: (52) Empty reply from server. TODO: Send error message back!!!

        basin_id = data.get("basin_id")
        attributes = data.get("attributes")

        print("bla2")

        # Check validity of attributes:
        if not attributes in ['basin', 'order_vect_segment']:
            LOGGER.error('Error: Wrong attributes: %s' % attributes)
            sys.exit(1)

        # Check validity of basin_id:
        try:
            int(basin_id)
        except ValueError as e:
            print('Basin id has to be integer!')
            sys.exit(1)

        print('Basin id:  %s' % basin_id)
        print('Attribute: %s' % attributes)

        print("bla3")


        ### Call R Script:
        ### Attention: Code to data is hard-coded in R-Script!
        path_command = "/home/mbuurman/work/instance_pygeoapi/pygeoapi/pygeoapi/pygeoapi/process/get_filtered_vector.r"
        cmd = ["/usr/bin/Rscript", "--vanilla", path_command, str(basin_id), attributes]
        print('Command:')
        print(cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        stdoutdata, stderrdata = p.communicate()

        print("bla4")


        ### Get return code and output
        print('Process exit code: %s' % p.returncode)
        stdouttext = stdoutdata.decode()
        stderrtext = stderrdata.decode()
        if len(stderrdata) > 0:
            err_and_out = '___PROCESS OUTPUT___\n___stdout___\n%s\n___stderr___\n%s\n___END___' % (stdouttext, stderrtext)
        else:
            err_and_out = '___PROCESS OUTPUT___\n___stdout___\n%s\n___(Nothing written to stderr)___\n___END___' % stdouttext
        print(err_and_out)


        ### Get return path from R
        # TODO: Getting the return like this, by parsing stdout and looking for a specific pattern, is absolutely dirty!! FIXME!
        if 'RETURNNNN' in stdouttext:
            tmp = stdouttext.split('RETURNNNN')
            return_from_r = tmp[len(tmp)-1].strip().strip('"')
            print('RETURN: "%s"' % return_from_r)

        # TODO: Need to find a way to return a file!!



        outputs = {
            'id': 'vector_file',
            'value': return_from_r
        }

        mimetype = 'application/json'
        return mimetype, outputs

    def __repr__(self):
        return f'<SnapToNetworkProcessor> {self.name}'


    def make_file_from_geojson(self, multipoint, input_coord_file_path, col_name_lat='lat', col_name_lon='lon', sep=','):

        print('Writing input coordinates from geojson into "%s"...' % input_coord_file_path)
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

        print('Now calling bash which calls grass/gdal...')
        print('Current directory: %s' % os.getcwd())
        bash_file = os.getcwd()+'/pygeoapi/process/snap_to_network.sh'
        cmd =[bash_file, path_coord_file, id_col_name, lon_col_name, lat_col_name,
              path_stream_tif, path_accumul_tif, method, str(distance), str(accumulation), snap_tmp_path, tmp_dir]
        print('GRASS command: %s' % cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        stdoutdata, stderrdata = p.communicate()
        print('Process exit code: %s' % p.returncode)
        print('Process output:\n____________\n%s\n_____(end of process stdout)_______' % stdoutdata.decode())
        if len(stderrdata.decode()) > 0:
            print('Process errors:\n____________\n%s\n_____(end of process stderr)_______' % stderrdata.decode())
        else:
            print('(Nothing written to stderr: "%s")' % stderrdata.decode())
        return snap_tmp_path


    def csv_to_geojson(self, snap_tmp_path):
        # Get results by reading them from result file!
        # This is how GeoJSON Multipoints look:
        # "{\"coordinates\": [[-17.25355, -44.885825], [-13.763611, -43.595833]], \"type\": \"MultiPoint\"}"
        result_multipoint = {"type": "MultiPoint", "coordinates":[]}
        print('Reading snapped points from GRASS result file "%s" and writing them into a GeoJSON Multipoint...' % snap_tmp_path)
        firstline = True
        with open(snap_tmp_path, 'r') as resultfile:
            for line in resultfile:

                # Ignore header line!
                if firstline:
                    firstline = False
                    continue

                line = line.strip()
                print('Found coordinate line: %s' % line) # TODO Understand why we get so many columns here!
                splitted = line.split()

                # Which columns?
                coord1, coord2 = splitted[1], splitted[2]
                print('Extracted these coordinates %s, %s' % (coord1, coord2))
                result_multipoint['coordinates'].append([coord2, coord1])
        print('Finished creating GeoJSON multipoint: %s' % geojson.dumps(result_multipoint))
        return result_multipoint
