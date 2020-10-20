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

__version__ = '0.9.dev0'

import os
import click
import locale
import pytz

DEFAULT_LANG = 'en_US.UTF-8'
locale.setlocale(locale.LC_ALL, os.environ.get('LANG', DEFAULT_LANG))
ENV_TZ = pytz.timezone(os.environ.get('TZ', 'Etc/UTC'))

from pygeoapi.openapi import generate_openapi_document

@click.group()
@click.version_option(version=__version__)
def cli():
    pass

@cli.command()
@click.option('--flask', 'server', flag_value="flask", default=True)
@click.option('--starlette', 'server', flag_value="starlette")
@click.pass_context
def serve(ctx, server):
    """Run the server with different daemon type (--flask is the default)"""

    if server == "flask":
        from pygeoapi.flask_app import serve as serve_flask
        ctx.forward(serve_flask)
        ctx.invoke(serve_flask)
    elif server == "starlette":
        from pygeoapi.starlette_app import serve as serve_starlette
        ctx.forward(serve_starlette)
        ctx.invoke(serve_starlette)
    else:
        raise click.ClickException('--flask/--starlette is required')


cli.add_command(generate_openapi_document)
