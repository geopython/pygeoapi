# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2021 Tom Kralidis
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

__version__ = '0.13.0'

import click
from pygeoapi.config import config
from pygeoapi.openapi import openapi


@click.group()
@click.version_option(version=__version__)
def cli():
    pass


@cli.command()
@click.option('--flask', 'server', flag_value="flask", default=True)
@click.option('--starlette', 'server', flag_value="starlette")
@click.option('--django', 'server', flag_value="django")
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
    elif server == "django":
        from pygeoapi.django_app import main as serve_django
        ctx.invoke(serve_django)
    else:
        raise click.ClickException('--flask/--starlette/--django is required')


cli.add_command(config)
cli.add_command(openapi)
