import os

os.environ['PYGEOAPI_CONFIG'] = 'pygeoapi-test-config.yml'
os.environ['PYGEOAPI_OPENAPI'] = 'pygeoapi-test-openapi.yml'

from pygeoapi.flask_app import APP

if __name__ == "__main__":
    APP.run()
