import os

from pygeoapi.flask_app import APP

os.environ['PYGEOAPI_CONFIG'] = 'pygeoapi-test-config.yml'
os.environ['PYGEOAPI_OPENAPI'] = 'pygeoapi-test-openapi.yml'


if __name__ == "__main__":
    APP.run()
