# =================================================================
#
# Authors: Tim-Hinnerk Heuer <th.heuer@gmail.com>
#
# Copyright (c) 2020 Tim-Hinnerk Heuer
#   (on behalf or Manaaki Whenua Landcare Research, New Zealand)
# Copyright (c) 2019 Just van den Broecke
# Copyright (c) 2019 Tom Kralidis
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

# Needs to be run like: python3 -m pytest

import pytest
from pygeoapi.provider.postgresql import PostgreSQLProvider


@pytest.fixture()
def config():
    return {
        "name": "PostgreSQL",
        "data": {
            "host": "127.0.0.1",
            "dbname": "test",
            "user": "postgres",
            "password": "postgres",
            "search_path": ["public"],
        },
        "id_field": "fid",
        "table": "nzlri_land_usage_capability_nztm_limited",
        "geom_field": "geom",
    }


def test_nztm_2194_projection(config):
    p = PostgreSQLProvider(config)
    feature_collection = p.query()
    assert (
        feature_collection["crs:epsg"] == 2193
    ), "Gets the correct projection for NZTM dataset"
