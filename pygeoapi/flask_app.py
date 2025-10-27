# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Norman Barker <norman.barker@gmail.com>
#
# Copyright (c) 2025 Tom Kralidis
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

"""Flask module providing the route paths to the api"""

import os
from typing import Union

import click
from flask import (Flask, Blueprint, make_response, request,
                   send_from_directory, Response, Request)

from pygeoapi.api import API, APIRequest, apply_gzip
import pygeoapi.api as core_api
import pygeoapi.api.coverages as coverages_api
import pygeoapi.api.environmental_data_retrieval as edr_api
import pygeoapi.api.itemtypes as itemtypes_api
import pygeoapi.api.maps as maps_api
import pygeoapi.api.processes as processes_api
import pygeoapi.api.stac as stac_api
import pygeoapi.api.tiles as tiles_api
from pygeoapi.openapi import load_openapi_document
from pygeoapi.config import get_config
from pygeoapi.util import get_mimetype, get_api_rules


# Function to return a WSGI application,
# passing the locations for the config and
# openapi files as variables, instead as environment variables
def make_wsgi_app(config_location: str, openapi_location: str) -> Flask:
    """
    Create a WSGI application
    Args:
        config_location (str): location of the pygeoapi config file
        openapi_location (str): location of the OpenAPI document file

    Returns:
        Flask WSGI application
    """
    config = get_config(config_path=config_location)
    openapi = load_openapi_document(pygeoapi_openapi=openapi_location)

    api_rules = get_api_rules(config)

    if config['server'].get('admin'):
        import pygeoapi.api.admin as admin_api
        from pygeoapi.api.admin import Admin

    static_folder = 'static'
    if 'templates' in config['server']:
        static_folder = config['server']['templates'].get('static', 'static')

    app = Flask(
        __name__,
        static_folder=static_folder,
        static_url_path='/static'
    )

    app.url_map.strict_slashes = api_rules.strict_slashes

    blueprint = Blueprint(
        'pygeoapi',
        __name__,
        static_folder=static_folder,
        url_prefix=api_rules.get_url_prefix('flask')
    )
    admin_blueprint = Blueprint(
        'admin',
        __name__,
        static_folder=static_folder,
        url_prefix=api_rules.get_url_prefix('flask')
    )

    # CORS: optionally enable from config.
    if config['server'].get('cors', False):
        try:
            from flask_cors import CORS
            CORS(app, CORS_EXPOSE_HEADERS=['*'])
        except ModuleNotFoundError:
            print('Python package flask-cors required for CORS support')

    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = config['server'].get(
        'pretty_print', True)

    api_ = API(config, openapi)

    ogc_schemas_location = config['server'].get('ogc_schemas_location')

    if (ogc_schemas_location is not None and
            not ogc_schemas_location.startswith('http')):
        # serve the OGC schemas locally

        if not os.path.exists(ogc_schemas_location):
            raise RuntimeError('OGC schemas misconfigured')

        @blueprint.route('/schemas/<path:path>', methods=['GET'])
        def schemas(path: str) -> Response:
            """
            Serve OGC schemas locally

            :param path: path of the OGC schema document

            :returns: HTTP response
            """

            full_filepath = os.path.join(ogc_schemas_location, path)
            dirname_ = os.path.dirname(full_filepath)
            basename_ = os.path.basename(full_filepath)

            path_ = dirname_.replace('..', '').replace('//', '').replace('./', '')  # noqa: E501

            if '..' in path_:
                return 'Invalid path', 400

            return send_from_directory(
                path_,
                basename_,
                mimetype=get_mimetype(basename_)
            )

    def execute_from_flask(
            api_function: callable,
            request: Request,
            *args,
            skip_valid_check: bool = False,
            alternative_api: Response = None,
            ) -> Response:
        """
        Executes API function from Flask

        :param api_function: API function
        :param request: request object
        :param *args: variable length additional arguments
        :param skip_validity_check: bool
        :param alternative_api: specify custom api instance such as Admin

        :returns: A Response instance
        """

        actual_api = api_ if alternative_api is None else alternative_api

        api_request = APIRequest.from_flask(request, actual_api.locales)

        content: Union[str, bytes]

        if not skip_valid_check and not api_request.is_valid():
            headers, status, content = actual_api.get_format_exception(api_request)  # noqa: E501
        else:
            headers, status, content = api_function(actual_api, api_request, *args)  # noqa: E501
            content = apply_gzip(headers, content)

        response = make_response(content, status)

        if headers:
            response.headers = headers
        return response

    @blueprint.route('/')
    def landing_page() -> Response:
        """
        OGC API landing page endpoint

        :returns: HTTP response
        """
        return execute_from_flask(core_api.landing_page, request)

    @blueprint.route('/openapi')
    def openapi() -> Response:
        """
        OpenAPI endpoint

        :returns: HTTP response
        """

        return execute_from_flask(core_api.openapi_, request)

    @blueprint.route('/conformance')
    def conformance() -> Response:
        """
        OGC API conformance endpoint

        :returns: HTTP response
        """

        return execute_from_flask(core_api.conformance, request)

    @blueprint.route('/TileMatrixSets/<tileMatrixSetId>')
    def get_tilematrix_set(tileMatrixSetId: str) -> Response:
        """
        OGC API TileMatrixSet endpoint

        :param tileMatrixSetId: identifier of tile matrix set

        :returns: HTTP response
        """
        return execute_from_flask(
            tiles_api.tilematrixset, request, tileMatrixSetId
        )

    @blueprint.route('/TileMatrixSets')
    def get_tilematrix_sets() -> Response:
        """
        OGC API TileMatrixSets endpoint

        :returns: HTTP response
        """
        return execute_from_flask(tiles_api.tilematrixsets, request)

    @blueprint.route('/collections')
    @blueprint.route('/collections/<path:collection_id>')
    def collections(collection_id: str = None) -> Response:
        """
        OGC API collections endpoint

        :param collection_id: collection identifier

        :returns: HTTP response
        """
        return execute_from_flask(
            core_api.describe_collections, request, collection_id
            )

    @blueprint.route('/collections/<path:collection_id>/schema')
    def collection_schema(collection_id: str) -> Response:
        """
        OGC API - collections schema endpoint

        :param collection_id: collection identifier

        :returns: HTTP response
        """

        return execute_from_flask(
            core_api.get_collection_schema, request, collection_id
            )

    @blueprint.route('/collections/<path:collection_id>/queryables')
    def collection_queryables(collection_id: str) -> Response:
        """
        OGC API collections queryables endpoint

        :param collection_id: collection identifier

        :returns: HTTP response
        """

        return execute_from_flask(
            itemtypes_api.get_collection_queryables, request, collection_id
            )

    @blueprint.route(
        '/collections/<path:collection_id>/items',
        methods=['GET', 'POST', 'OPTIONS'],
        provide_automatic_options=False
    )
    @blueprint.route(
        '/collections/<path:collection_id>/items/<path:item_id>',
        methods=['GET', 'PUT', 'DELETE', 'OPTIONS'],
        provide_automatic_options=False
    )
    def collection_items(collection_id: str, item_id: str = None) -> Response:
        """
        OGC API collections items endpoint

        :param collection_id: collection identifier
        :param item_id: item identifier

        :returns: HTTP response
        """

        if item_id is None:
            if request.method == 'POST':  # filter or manage items
                if request.content_type is not None:
                    if request.content_type == 'application/geo+json':
                        return execute_from_flask(
                            itemtypes_api.manage_collection_item,
                            request, 'create', collection_id,
                            skip_valid_check=True)
                    else:
                        return execute_from_flask(
                            itemtypes_api.get_collection_items, request,
                            collection_id, skip_valid_check=True)
            elif request.method == 'OPTIONS':
                return execute_from_flask(
                    itemtypes_api.manage_collection_item, request, 'options',
                    collection_id, skip_valid_check=True)
            else:  # GET: list items
                return execute_from_flask(
                    itemtypes_api.get_collection_items,
                    request, collection_id,
                    skip_valid_check=True)

        elif request.method == 'DELETE':
            return execute_from_flask(
                itemtypes_api.manage_collection_item,
                request, 'delete', collection_id, item_id,
                skip_valid_check=True)
        elif request.method == 'PUT':
            return execute_from_flask(
                itemtypes_api.manage_collection_item,
                request, 'update', collection_id, item_id,
                skip_valid_check=True)
        elif request.method == 'OPTIONS':
            return execute_from_flask(
                itemtypes_api.manage_collection_item,
                request, 'options', collection_id, item_id,
                skip_valid_check=True)
        else:
            return execute_from_flask(
                itemtypes_api.get_collection_item, request,
                collection_id, item_id)

    @blueprint.route('/collections/<path:collection_id>/coverage')
    def collection_coverage(collection_id: str) -> Response:
        """
        OGC API - Coverages coverage endpoint

        :param collection_id: collection identifier

        :returns: HTTP response
        """

        return execute_from_flask(
            coverages_api.get_collection_coverage, request,
            collection_id, skip_valid_check=True
            )

    @blueprint.route('/collections/<path:collection_id>/tiles')
    def get_collection_tiles(collection_id: str) -> Response:
        """
        OGC open api collections tiles access point

        :param collection_id: collection identifier

        :returns: HTTP response
        """

        return execute_from_flask(
            tiles_api.get_collection_tiles, request, collection_id)

    @blueprint.route('/collections/<path:collection_id>/tiles/<tileMatrixSetId>')  # noqa E501
    @blueprint.route('/collections/<path:collection_id>/tiles/<tileMatrixSetId>/metadata')  # noqa E501
    def get_collection_tiles_metadata(
            collection_id: str, tileMatrixSetId: str) -> Response:
        """
        OGC open api collection tiles service metadata

        :param collection_id: collection identifier
        :param tileMatrixSetId: identifier of tile matrix set

        :returns: HTTP response
        """

        return execute_from_flask(
            tiles_api.get_collection_tiles_metadata,
            request, collection_id, tileMatrixSetId,
            skip_valid_check=True)

    @blueprint.route('/collections/<path:collection_id>/tiles/\
    <tileMatrixSetId>/<tileMatrix>/<tileRow>/<tileCol>')
    def get_collection_tiles_data(
            collection_id: str, tileMatrixSetId: str,
            tileMatrix: str, tileRow: str, tileCol: str) -> Response:
        """
        OGC open api collection tiles service data

        :param collection_id: collection identifier
        :param tileMatrixSetId: identifier of tile matrix set
        :param tileMatrix: identifier of {z} matrix index
        :param tileRow: identifier of {y} matrix index
        :param tileCol: identifier of {x} matrix index

        :returns: HTTP response
        """

        return execute_from_flask(
            tiles_api.get_collection_tiles_data,
            request, collection_id, tileMatrixSetId, tileMatrix,
            tileRow, tileCol, skip_valid_check=True
        )

    @blueprint.route('/collections/<collection_id>/map')
    @blueprint.route('/collections/<collection_id>/styles/<style_id>/map')
    def collection_map(collection_id: str, style_id: str = None) -> Response:
        """
        OGC API - Maps map render endpoint

        :param collection_id: collection identifier
        :param style_id: style identifier

        :returns: HTTP response
        """

        return execute_from_flask(
            maps_api.get_collection_map, request, collection_id, style_id
        )

    @blueprint.route('/processes')
    @blueprint.route('/processes/<process_id>')
    def get_processes(process_id: str = None) -> Response:
        """
        OGC API - Processes description endpoint

        :param process_id: process identifier

        :returns: HTTP response
        """

        return execute_from_flask(
            processes_api.describe_processes, request, process_id)

    @blueprint.route('/jobs')
    @blueprint.route(
        '/jobs/<job_id>', methods=['GET', 'DELETE']
        )
    def get_jobs(job_id: str = None) -> Response:
        """
        OGC API - Processes jobs endpoint

        :param job_id: job identifier

        :returns: HTTP response
        """

        if job_id is None:
            return execute_from_flask(processes_api.get_jobs, request)
        else:
            if request.method == 'DELETE':  # dismiss job
                return execute_from_flask(
                    processes_api.delete_job, request, job_id
                )
            else:  # Return status of a specific job
                return execute_from_flask(
                    processes_api.get_jobs, request, job_id
                )

    @blueprint.route('/processes/<process_id>/execution', methods=['POST'])
    def execute_process_jobs(process_id: str) -> Response:
        """
        OGC API - Processes execution endpoint

        :param process_id: process identifier

        :returns: HTTP response
        """

        return execute_from_flask(
            processes_api.execute_process, request, process_id
        )

    @blueprint.route(
        '/jobs/<job_id>/results',
        methods=['GET']
    )
    def get_job_result(job_id: str = None) -> Response:
        """
        OGC API - Processes job result endpoint

        :param job_id: job identifier

        :returns: HTTP response
        """

        return execute_from_flask(
            processes_api.get_job_result, request, job_id
        )

    @blueprint.route('/collections/<path:collection_id>/position')
    @blueprint.route('/collections/<path:collection_id>/area')
    @blueprint.route('/collections/<path:collection_id>/cube')
    @blueprint.route('/collections/<path:collection_id>/radius')
    @blueprint.route('/collections/<path:collection_id>/trajectory')
    @blueprint.route('/collections/<path:collection_id>/corridor')
    @blueprint.route('/collections/<path:collection_id>/locations/<location_id>')  # noqa E501
    @blueprint.route('/collections/<path:collection_id>/locations')
    @blueprint.route('/collections/<path:collection_id>/instances/<instance_id>/position')  # noqa E501
    @blueprint.route('/collections/<path:collection_id>/instances/<instance_id>/area')  # noqa E501
    @blueprint.route('/collections/<path:collection_id>/instances/<instance_id>/cube')  # noqa E501
    @blueprint.route('/collections/<path:collection_id>/instances/<instance_id>/radius')  # noqa E501
    @blueprint.route('/collections/<path:collection_id>/instances/<instance_id>/trajectory')  # noqa E501
    @blueprint.route('/collections/<path:collection_id>/instances/<instance_id>/corridor')  # noqa E501
    @blueprint.route('/collections/<path:collection_id>/instances/<instance_id>/locations/<location_id>')  # noqa E501
    @blueprint.route('/collections/<path:collection_id>/instances/<instance_id>/locations')  # noqa E501
    @blueprint.route('/collections/<path:collection_id>/instances/<instance_id>')  # noqa E501
    @blueprint.route('/collections/<path:collection_id>/instances')
    def get_collection_edr_query(
            collection_id: str, instance_id: str = None,
            location_id: str = None
            ) -> Response:
        """
        OGC EDR API endpoints

        :param collection_id: collection identifier
        :param instance_id: instance identifier
        :param location_id: location id of a /locations/<location_id> query

        :returns: HTTP response
        """

        if (
            request.path.endswith('instances') or
            (instance_id is not None and request.path.endswith(instance_id))
        ):
            return execute_from_flask(
                edr_api.get_collection_edr_instances, request, collection_id,
                instance_id
            )

        if location_id:
            query_type = 'locations'
        else:
            query_type = request.path.split('/')[-1]

        return execute_from_flask(
            edr_api.get_collection_edr_query, request, collection_id,
            instance_id, query_type, location_id, skip_valid_check=True
        )

    @blueprint.route('/stac-api')
    def stac_landing_page() -> Response:
        """
        STAC API landing page endpoint

        :returns: HTTP response
        """

        return execute_from_flask(stac_api.landing_page, request)

    @blueprint.route('/stac-api/search', methods=['GET', 'POST'])
    def stac_search() -> Response:
        """
        STAC API search endpoint

        :returns: HTTP response
        """

        return execute_from_flask(stac_api.search, request)

    @blueprint.route('/stac')
    def stac_catalog_root() -> Response:
        """
        STAC root endpoint

        :returns: HTTP response
        """

        return execute_from_flask(stac_api.get_stac_root, request)

    @blueprint.route('/stac/<path:path>')
    def stac_catalog_path(path: str) -> Response:
        """
        STAC path endpoint

        :param path: path

        :returns: HTTP response
        """

        return execute_from_flask(stac_api.get_stac_path, request, path)

    @admin_blueprint.route('/admin/config', methods=['GET', 'PUT', 'PATCH'])
    def admin_config() -> Response:
        """
        Admin endpoint

        :returns: HTTP response
        """

        if request.method == 'GET':
            return execute_from_flask(
                admin_api.get_config_, request, alternative_api=admin_
            )

        elif request.method == 'PUT':
            return execute_from_flask(
                admin_api.put_config, request, alternative_api=admin_
            )

        elif request.method == 'PATCH':
            return execute_from_flask(
                admin_api.patch_config, request, alternative_api=admin_
            )

    @admin_blueprint.route('/admin/config/resources', methods=['GET', 'POST'])
    def admin_config_resources() -> Response:
        """
        Resources endpoint

        :returns: HTTP response
        """

        if request.method == 'GET':
            return execute_from_flask(
                admin_api.get_resources, request, alternative_api=admin_
            )

        elif request.method == 'POST':
            return execute_from_flask(
                admin_api.post_resource, request, alternative_api=admin_
            )

    @admin_blueprint.route(
        '/admin/config/resources/<resource_id>',
        methods=['GET', 'PUT', 'PATCH', 'DELETE'])
    def admin_config_resource(resource_id: str) -> Response:
        """
        Resource endpoint

        :returns: HTTP response
        """

        if request.method == 'GET':
            return execute_from_flask(
                admin_api.get_resource, request,
                resource_id, alternative_api=admin_
            )

        elif request.method == 'DELETE':
            return execute_from_flask(
                admin_api.delete_resource, request,
                resource_id, alternative_api=admin_
            )

        elif request.method == 'PUT':
            return execute_from_flask(
                admin_api.put_resource, request,
                resource_id, alternative_api=admin_
            )

        elif request.method == 'PATCH':
            return execute_from_flask(
                admin_api.patch_resource, request,
                resource_id, alternative_api=admin_
            )

    app.register_blueprint(blueprint)

    if config['server'].get('admin'):
        admin_ = Admin(config, openapi)
        app.register_blueprint(admin_blueprint)

    return app


if os.environ.get('PYGEOAPI_DISABLE_ENV_CONFIGS', 'false') == 'false':
    APP = make_wsgi_app(
        config_location=None,
        openapi_location=None
    )
    config = get_config()

    @click.command()
    @click.pass_context
    @click.option('--debug', '-d', default=False, is_flag=True, help='debug')
    def serve(
            ctx: click.Context, server: str = None, debug: bool = False
            ) -> None:
        """
        Serve pygeoapi via Flask. Runs pygeoapi
        as a flask server. Not recommend for production.

        :param server: `string` of server type
        :param debug: `bool` of whether to run in debug mode

        :returns: void
        """

        # setup_logger(CONFIG['logging'])
        APP.run(debug=True, host=config['server']['bind']['host'],
                port=config['server']['bind']['port'])

if __name__ == '__main__':  # run locally, for testing
    serve()
