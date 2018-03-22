#Needs to be run like: pytest -s test_sqlite_provider.py
import pytest
import sqlite3
import os
from pygeoapi.provider.sqlite import SQLiteProvider



db_path="/home/jorge/Projects/pygeoapi/tests/data/ne_110m_lakes.sqlite"

@pytest.fixture()
def config():
    return {
            'name': 'Sqlite',
            'data': db_path,
            'id_field': "OGC_FID",
            'table': 'ne_110m_lakes'}


def test_query(config):
   p = SQLiteProvider(**config)
   results =p.query()

   assert len(results['features']) == 1
   assert results['features'][0]['id'] == '123-456'
   print(results)
