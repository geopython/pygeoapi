# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Norman Barker <norman.barker@gmail.com>
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

import click
import connexion

from pygeoapi.log import setup_logger
from pygeoapi.config import settings


@click.command()
@click.pass_context
@click.option('--host', '-h', default='localhost', help='Hostname')
@click.option('--port', '-p', default=5000, help='port')
@click.option('--debug', '-d', default=False, is_flag=True, help='debug')
def serve(ctx, host, port, debug=False):
    """Serve pygeoapi via Flask"""

    if port is not None:
        port_ = port
    else:
        port_ = settings['server']['port']
    if host is not None:
        host_ = host
    else:
        host_ = settings['server']['host']

    app = connexion.FlaskApp(__name__, port=port_, specification_dir='.')

    hostport = '{}:{}'.format(host_, port_)

    api = app.add_api(settings['swagger'], debug=debug, strict_validation=True,
                      arguments={'host': hostport, 'config': settings})

    settings['api'] = api.specification

    setup_logger()
    app.run()
