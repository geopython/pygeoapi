# =================================================================
#
# Authors: Francesco Bartoli <francesco.bartoli@geobeyond.it>
#          Luca Delucchi <lucadeluge@gmail.com>
#          Krishna Lodha <krishnaglodha@gmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 Francesco Bartoli
# Copyright (c) 2022 Luca Delucchi
# Copyright (c) 2022 Krishna Lodha
# Copyright (c) 2022 Tom Kralidis
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

"""django_ URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import (
    path,
)
from django.conf import settings
from django.conf.urls.static import static

from . import views

urlpatterns = [
    path('', views.landing_page, name='landing-page'),
    path('openapi/', views.openapi, name='openapi'),
    path('conformance/', views.conformance, name='conformance'),
    path('collections/', views.collections, name='collections'),
    path(
        'collections/<str:collection_id>',
        views.collections,
        name='collection-detail',
    ),
    path(
        'collections/<str:collection_id>/queryables/',
        views.collection_queryables,
        name='collection-queryables',
    ),
    path(
        'collections/<str:collection_id>/items/',
        views.collection_items,
        name='collection-items',
    ),
    path(
        'collections/<str:collection_id>/items/<str:item_id>',
        views.collection_item,
        name='collection-item',
    ),
    path(
        'collections/<str:collection_id>/coverage/',
        views.collection_coverage,
        name='collection-coverage',
    ),
    path(
        'collections/<str:collection_id>/coverage/domainset/',
        views.collection_coverage_domainset,
        name='collection-coverage-domainset',
    ),
    path(
        'collections/<str:collection_id>/coverage/rangetype/',
        views.collection_coverage_rangetype,
        name='collection-coverage-rangetype',
    ),
    path(
        'collections/<str:collection_id>/tiles/',
        views.collection_tiles,
        name='collection-tiles',
    ),
    path(
        'collections/<str:collection_id>/tiles/<str:tileMatrixSetId>/metadata',
        views.collection_tiles_metadata,
        name='collection-tiles-metadata',
    ),
    path(
        'collections/<str:collection_id>/tiles/\
        <str:tileMatrixSetId>/<str:tile_matrix>/<str:tileRow>/<str:tileCol>',
        views.collection_item_tiles,
        name='collection-item-tiles',
    ),
    path(
        'collections/<str:collection_id>/position',
        views.get_collection_edr_query,
        name='collection-edr-position',
    ),
    path(
        'collections/<str:collection_id>/area',
        views.get_collection_edr_query,
        name='collection-edr-area',
    ),
    path(
        'collections/<str:collection_id>/cube',
        views.get_collection_edr_query,
        name='collection-edr-cube',
    ),
    path(
        'collections/<str:collection_id>/trajectory',
        views.get_collection_edr_query,
        name='collection-edr-trajectory',
    ),
    path(
        'collections/<str:collection_id>/corridor',
        views.get_collection_edr_query,
        name='collection-edr-corridor',
    ),
    path(
        'collections/<str:collection_id>/instances/<str:instance_id>/position',
        views.get_collection_edr_query,
        name='collection-edr-instance-position',
    ),
    path(
        'collections/<str:collection_id>/instances/<str:instance_id>/area',
        views.get_collection_edr_query,
        name='collection-edr-instance-area',
    ),
    path(
        'collections/<str:collection_id>/instances/<str:instance_id>/cube',
        views.get_collection_edr_query,
        name='collection-edr-instance-cube',
    ),
    path(
        'collections/<str:collection_id>/instances/<str:instance_id>/trajectory',  # noqa
        views.get_collection_edr_query,
        name='collection-edr-instance-trajectory',
    ),
    path(
        'collections/<str:collection_id>/instances/<str:instance_id>/corridor',
        views.get_collection_edr_query,
        name='collection-edr-instance-corridor',
    ),
    path('processes/', views.processes, name='processes'),
    path('processes/<str:process_id>', views.processes, name='process-detail'),
    path('jobs/', views.jobs, name='jobs'),
    path('jobs/<str:job_id>', views.jobs, name='job'),
    path(
        'jobs/<str:job_id>/results/',
        views.job_results,
        name='job-results',
    ),
    path(
        'jobs/<str:job_id>/results/<str:resource>',
        views.job_results_resource,
        name='job-results-resource',
    ),
    path('stac/', views.stac_catalog_root, name='stac-catalog-root'),
    path('stac/<str:path>', views.stac_catalog_path, name='stac-catalog-path'),
    path(
        'stac/search/', views.stac_catalog_search, name='stac-catalog-search'
    ),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
