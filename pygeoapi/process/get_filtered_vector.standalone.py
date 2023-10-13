import logging
import argparse
import subprocess
import geojson
import os
import sys
import tempfile

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

LOGGER.info('Starting "get_filtered_vector as standalone!"')

if __name__ == '__main__':

    ### Get and validate input params:
    LOGGER.debug('Getting the input parameters...')
    parser = argparse.ArgumentParser(
                        prog='Calling get_filtered_vector tool via python',
                        description='This program wants to ...')
    parser.add_argument('--basin_id', default='481051', help='BLA.')
    parser.add_argument('--attributes', default='basin', help='BLA')
    args = parser.parse_args()
    basin_id = args.basin_id
    attributes = args.attributes

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

    LOGGER.info('Basin id:  %s' % basin_id)
    LOGGER.info('Attribute: %s' % attributes)


    ### Call R Script:
    ### Attention: Code to data is hard-coded in R-Script!
    path_command = "/home/mbuurman/work/instance_pygeoapi/pygeoapi/pygeoapi/pygeoapi/process/get_filtered_vector.r"
    cmd = ["/usr/bin/Rscript", "--vanilla", path_command, basin_id, attributes]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = p.communicate()


    ### Get return code and output
    LOGGER.debug('Process exit code: %s' % p.returncode)
    stdouttext = stdoutdata.decode()
    stderrtext = stderrdata.decode()
    if len(stderrdata) > 0:
        err_and_out = '___PROCESS OUTPUT___\n___stdout___\n%s\n___stderr___\n%s\n___END___' % (stdouttext, stderrtext)
    else:
        err_and_out = '___PROCESS OUTPUT___\n___stdout___\n%s\n___(Nothing written to stderr)___\n___END___' % stdouttext
    LOGGER.debug(err_and_out)


    ### Get return path from R
    # TODO: Getting the return like this, by parsing stdout and looking for a specific pattern, is absolutely dirty!! FIXME!
    if 'RETURNNNN' in stdouttext:
        tmp = stdouttext.split('RETURNNNN')
        return_from_r = tmp[len(tmp)-1].strip().strip('"')
        print('RETURN: "%s"' % return_from_r)

    # return return_from_r

