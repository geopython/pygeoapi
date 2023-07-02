# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2019 Tom Kralidis
#           (c) 2023 Ricardo Garcia Silva
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
from typing import Dict

from pygeoapi.plugin import load_plugin
from pygeoapi.process.manager.base import BaseManager

LOGGER = logging.getLogger(__name__)


def get_manager(config: Dict) -> BaseManager:
    """Instantiate process manager from the supplied configuration.

    :param config: pygeoapi configuration

    :returns: The pygeoapi process manager object
    """
    manager_conf = config.get('server', {}).get(
        'manager',
        {
            'name': 'Dummy',
            'connection': None,
            'output_dir': None
        }
    )
    processes_conf = {}
    for id_, resource_conf in config.get('resources', {}).items():
        if resource_conf.get('type') == 'process':
            processes_conf[id_] = resource_conf
    manager_conf['processes'] = processes_conf
    if manager_conf.get('name') == 'Dummy':
        LOGGER.info('Starting dummy manager')
    return load_plugin('process_manager', manager_conf)
