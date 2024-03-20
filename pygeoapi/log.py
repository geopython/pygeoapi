# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
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

"""Logging system"""

import logging
from logging.handlers import RotatingFileHandler
from logging.handlers import TimedRotatingFileHandler
import sys

LOGGER = logging.getLogger(__name__)


def setup_logger(logging_config):
    """
    Setup configuration

    :param logging_config: logging specific configuration

    :returns: void (creates logging instance)
    """

    default_log_format = (
        '[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s'
    )
    default_date_format = '%Y-%m-%dT%H:%M:%SZ'

    log_format = logging_config.get('logformat', default_log_format)
    date_format = logging_config.get('dateformat', default_date_format)

    loglevels = {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'NOTSET': logging.NOTSET
    }

    loglevel = loglevels[logging_config['level']]

    if 'logfile' in logging_config:
        rotation = logging_config.get('rotation')
        if rotation:
            rotate_mode = rotation.get('mode')

            rotate_backup_count = rotation.get('backup_count', 0)

            if rotate_mode == 'size':
                rotate_max_bytes = rotation.get('max_bytes', 0)

                logging.basicConfig(
                    handlers=[
                        RotatingFileHandler(
                            filename=logging_config['logfile'],
                            maxBytes=rotate_max_bytes,
                            backupCount=rotate_backup_count
                        )
                    ],
                    level=loglevel,
                    datefmt=date_format,
                    format=log_format,
                )
            elif rotate_mode == 'time':
                rotate_when = rotation.get('when', 'h')
                rotate_interval = rotation.get('interval', 1)

                logging.basicConfig(
                    handlers=[
                        TimedRotatingFileHandler(
                            filename=logging_config['logfile'],
                            when=rotate_when,
                            interval=rotate_interval,
                            backupCount=rotate_backup_count
                        )
                    ],
                    level=loglevel,
                    datefmt=date_format,
                    format=log_format
                )
            else:
                raise Exception(f'Invalid rotation mode:{rotate_mode}')
        else:
            logging.basicConfig(
                level=loglevel,
                datefmt=date_format,
                format=log_format,
                filename=logging_config['logfile']
            )
    else:
        logging.basicConfig(
            level=loglevel,
            datefmt=date_format,
            format=log_format,
            stream=sys.stdout
        )

    LOGGER.debug('Logging initialized')
    return
