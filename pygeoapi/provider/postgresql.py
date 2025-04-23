

from pygeoapi.provider.sql import GenericSQLProvider


class PostgreSQLProvider(GenericSQLProvider):
    driver_name = 'postgresql+psycopg2'
    extra_conn_args = {
      'client_encoding': 'utf8',
      'application_name': 'pygeoapi'
    } 