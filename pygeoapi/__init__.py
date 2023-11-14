# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2021 Tom Kralidis
# Copyright (c) 2023 Ricardo Garcia Silva
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

__version__ = '0.16.dev0'

import click
import os
import sys
try:
    # importlib.metadata is part of Python's standard library from 3.8
    from importlib.metadata import entry_points
except ImportError:
    from importlib_metadata import entry_points
from pathlib import Path

import pygeoapi.util
import pygeoapi.api
from pygeoapi.config import config as config_click_group
from pygeoapi.openapi import openapi as openapi_click_group


def _find_plugins():
    """
    A decorator to find pygeoapi CLI plugins provided by third-party packages.

    pygeoapi plugins can hook into the pygeoapi CLI by providing their CLI
    functions and then using an entry_point named 'pygeoapi'.
    """

    def decorator(click_group):
        try:
            found_entrypoints = entry_points(group="pygeoapi")
        except TypeError:
            # earlier versions of importlib_metadata did not have the
            # `group` kwarg. More detail:
            #
            # https://github.com/geopython/pygeoapi/issues/1241#issuecomment-1536128897  # noqa: E501
            for group, entries in entry_points().items():
                if group == "pygeoapi":
                    found_entrypoints = entries
                    break
            else:
                found_entrypoints = []
        for entry_point in found_entrypoints:
            try:
                click_group.add_command(entry_point.load())
            except Exception as err:
                print(err)
        return click_group

    return decorator


@click.group()
@click.pass_context
@click.version_option(version=__version__)
@click.option(
    '-c',
    '--pygeoapi-config',
    envvar='PYGEOAPI_CONFIG',
    required=True,
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        path_type=Path
    )
)
@click.option(
    '--pygeoapi-openapi',
    envvar='PYGEOAPI_OPENAPI',
    required=True,
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        path_type=Path
    )
)
def cli(ctx: click.Context, pygeoapi_config, pygeoapi_openapi):
    print(f'{pygeoapi_config=}')
    print(f'{pygeoapi_openapi=}')
    ctx.ensure_object(dict)
    ctx.obj.update(
        {
            'pygeoapi_config_path': pygeoapi_config,
            'pygeoapi_openapi_path': pygeoapi_openapi,
            'pygeoapi_config': pygeoapi.util.get_config_from_path(
                pygeoapi_config),
            'pygeoapi_openapi': pygeoapi.util.get_openapi_from_path(
                pygeoapi_openapi)

        }
    )


@_find_plugins()
@cli.group()
def plugins():
    """Additional commands provided by third-party pygeoapi plugins"""
    pass


@cli.command(context_settings={'ignore_unknown_options': True})
@click.option('--flask', 'server', flag_value="flask", default=True)
@click.option('--starlette', 'server', flag_value="starlette")
@click.option('--django', 'server', flag_value="django")
@click.option(
    '--debug',
    is_flag=True,
    help="Whether to run with debug turned on or not"
)
@click.argument(
    'extra-gunicorn-args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def serve(ctx, server, debug, extra_gunicorn_args):
    """Run the server with different daemon type (--flask is the default)

    EXTRA_GUNICORN_ARGS - pass additional arguments to be forwarded to the
    gunicorn web server. These will overwrite any pygeoapi-specific gunicorn
    configuration
    \f
    """

    bind_address = ctx.obj['pygeoapi_config']['server']['bind']['host']
    bind_port = ctx.obj['pygeoapi_config']['server']['bind']['port']
    gunicorn_params = ['gunicorn']
    if server == 'flask':
        gunicorn_params.append(
            f'pygeoapi.flask_app:create_app("{ctx.obj["pygeoapi_config_path"]}", "{ctx.obj["pygeoapi_openapi_path"]}")'
        )
        gunicorn_params.extend(
            [
                f'--bind={bind_address}:{bind_port}',
                f'--error-logfile=-',
                f'--access-logfile=-',
            ]
        )
        if debug:
            gunicorn_params.extend(
                [
                    '--workers=1',
                    '--reload',
                    f'--log-level=debug',
                ]
            )
        else:
            log_level = ctx.obj['pygeoapi_config']['logging']['level']
            gunicorn_params.append(f'--log-level={log_level.lower()}')
    elif server == 'django':
        ...
    elif server == 'starlette':
        gunicorn_params.append(
            f'pygeoapi.starlette_app:create_app("{ctx.obj["pygeoapi_config_path"]}", "{ctx.obj["pygeoapi_openapi_path"]}")'
        )
        ...

    gunicorn_params.extend(extra_gunicorn_args)
    print(f"About to exec gunicorn with {gunicorn_params=}")
    sys.stdout.flush()
    sys.stderr.flush()
    os.execvp('gunicorn', gunicorn_params)

    # elif server == "starlette":
    #     from pygeoapi.starlette_app import serve as serve_starlette
    #     ctx.forward(serve_starlette)
    #     ctx.invoke(serve_starlette)
    # elif server == "django":
    #     from pygeoapi.django_app import main as serve_django
    #     ctx.invoke(serve_django)
    # else:
    #     raise click.ClickException('--flask/--starlette/--django is required')


cli.add_command(config_click_group)
cli.add_command(openapi_click_group)
