# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#
#
# Copyright (c) 2019 Francesco Bartoli
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
""" Starlette module providing the route paths to the api"""

import os

import click

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
import uvicorn

from pygeoapi.api import API
from pygeoapi.util import yaml_load

app = Starlette()

CONFIG = None

if 'PYGEOAPI_CONFIG' not in os.environ:
    raise RuntimeError('PYGEOAPI_CONFIG environment variable not set')

with open(os.environ.get('PYGEOAPI_CONFIG')) as fh:
    CONFIG = yaml_load(fh)

# CORS: optionally enable from config.
if CONFIG['server'].get('cors', False):
    from starlette.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=['*'])


api_ = API(CONFIG)


@app.route('/')
async def root(request: Request):
    """
    HTTP root content of pygeoapi. Intro page access point
    :returns: HTTP response
    """
    headers, status_code, content = api_.root(request.headers, request.query_params)

    response = Response(content=content, status_code=status_code)
    if headers:
        response.headers.update(headers)

    return response


@click.command()
@click.pass_context
@click.option('--debug', '-d', default=False, is_flag=True, help='debug')
def serve(ctx, server, debug=False):
    """
    Serve pygeoapi via Starlette. Runs pygeoapi
    as a uvicorn server. Not recommend for production.
    :param debug: `bool` of whether to run in debug mode
    :returns void
    """

#    setup_logger(CONFIG['logging'])
    uvicorn.run(app, debug=True, host=api_.config['server']['bind']['host'],
            port=api_.config['server']['bind']['port'])


if __name__ == "__main__": # run locally, for testing
    serve()