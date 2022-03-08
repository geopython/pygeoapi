"""django_pygeoapi URL Configuration

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

from . import views

urlpatterns = [
    path("", views.landing_page, name="landing-page"),
    path("openapi/", views.openapi, name="openapi"),
    path("conformance/", views.conformance, name="conformance"),
    path("collections/", views.collections, name="collections"),
    path(
        "collections/<str:collection_id>",
        views.collections,
        name="collection-detail",
    ),
    path(
        "collections/<str:collection_id>/queryables/",
        views.collection_queryables,
        name="collection-queryables",
    ),
    path(
        "collections/<str:collection_id>/items/",
        views.collection_items,
        name="collection-items",
    ),
    path(
        "collections/<str:collection_id>/items/<str:item_id>",
        views.collection_item,
        name="collection-item",
    ),
    path(
        "collections/<str:collection_id>/coverage/",
        views.collection_coverage,
        name="collection-coverage",
    ),
    path(
        "collections/<str:collection_id>/coverage/domainset/",
        views.collection_coverage_domainset,
        name="collection-coverage-domainset",
    ),
    path(
        "collections/<str:collection_id>/coverage/rangetype/",
        views.collection_coverage_rangetype,
        name="collection-coverage-rangetype",
    ),
    path(
        "collections/<str:collection_id>/tiles/",
        views.collection_tiles,
        name="collection-tiles",
    ),
    path(
        "collections/<str:collection_id>/tiles/<str:tileMatrixSetId>/metadata",
        views.collection_tiles_metadata,
        name="collection-tiles-metadata",
    ),
    path(
        "collections/<str:collection_id>/tiles/\
        <str:tileMatrixSetId>/<str:tile_matrix>/<str:tileRow>/<str:tileCol>",
        views.collection_item_tiles,
        name="collection-item-tiles",
    ),
    path("processes/", views.processes, name="processes"),
    path("processes/<str:process_id>", views.processes, name="process-detail"),
    path("jobs/", views.process_jobs, name="process-jobs"),
    path("jobs/<str:job_id>", views.process_jobs, name="process-job"),
    path(
        "jobs/<str:job_id>/results/",
        views.process_job_results,
        name="process-job-results",
    ),
    path(
        "jobs/<str:job_id>/results/<str:resource>",
        views.process_job_results_resource,
        name="process-job-results-resource",
    ),
    path("stac/", views.stac_catalog_root, name="stac-catalog-root"),
    path("stac/<str:path>", views.stac_catalog_path, name="stac-catalog-path"),
    path(
        "stac/search/", views.stac_catalog_search, name="stac-catalog-search"
    ),
]
