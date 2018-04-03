# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2018 Tom Kralidis
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
import sys

LOGGER = logging.getLogger(__name__)


def setup_logger(logging_config):
    """
    Setup configuration

    :param logging_config: logging specific configuration

    :returns: void (creates logging instance)
    """

    log_format = \
        '[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s'

    loglevels = {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'NOTSET': logging.NOTSET,
    }
    formatter = logging.Formatter(log_format)

    log_handler = logging.NullHandler()

    if 'level' in logging_config:
        loglevel = loglevels[logging_config['level']]
        log_handler = logging.StreamHandler(sys.stdout)

    if 'logfile' in logging_config:
        log_handler = logging.FileHandler(logging_config['logfile'])

    log_handler.setLevel(loglevel)
    log_handler.setFormatter(formatter)

    LOGGER.addHandler(log_handler)
    LOGGER.debug('Logging initialized')
    return
