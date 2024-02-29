from http import HTTPStatus
import sys
import os
from unittest import mock

import django
import pytest
from django.test import Client

from .util import get_test_file_path


@pytest.fixture
@mock.patch.dict(os.environ, {
    "DJANGO_SETTINGS_MODULE": "django_.settings",
    "PYGEOAPI_CONFIG": get_test_file_path('pygeoapi-test-config.yml'),
    "PYGEOAPI_OPENAPI": get_test_file_path('pygeoapi-test-openapi.yml')
})
@mock.patch.object(sys, "path", sys.path + ["./pygeoapi"])
def django_():
    django.setup()
    return django


def test_django_landing_page_loads(django_):
    response = Client(SERVER_NAME="localhost").get("/")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["title"] == "pygeoapi default instance"


def test_django_edr_without_instance_id(django_):
    edr_position_query = ("/collections/icoads-sst/position?coords="
                          "POINT(12.779895 55.783523)&f=json")
    response = Client(SERVER_NAME="localhost").get(edr_position_query)

    assert response.status_code == HTTPStatus.OK
    # Validate CoverageJSON is returned
    response_json = response.json()
    assert response_json["type"] == "Coverage"
    assert response_json["domain"]["domainType"] == "Grid"
