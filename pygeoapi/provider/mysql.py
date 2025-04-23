
from pygeoapi.provider.sql import GenericSQLProvider


class MySQLProvider(GenericSQLProvider):
    driver_name = 'mysql+pymysql'
    extra_conn_args = {
        'charset': 'utf8mb4',
    }