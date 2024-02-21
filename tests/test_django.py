from http import HTTPStatus
import sys
import os
from unittest import mock

import django
from django.test import Client


@mock.patch.dict(os.environ, {"DJANGO_SETTINGS_MODULE": "django_.settings"})
@mock.patch.object(sys, "path", sys.path + ["./pygeoapi"])
def test_django_landing_page_loads():
    django.setup()

    response = Client(SERVER_NAME="localhost").get("/")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["title"] == "pygeoapi default instance"
