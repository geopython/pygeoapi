FROM geopython/pygeoapi:latest

COPY ./ext_data /ext_data
COPY ./sparql.py /pygeoapi/pygeoapi/provider/sparql.py
COPY ./plugin.py /pygeoapi/pygeoapi/plugin.py
COPY ./sparql.pygeoapi.config.yml /pygeoapi/local.config.yml
RUN ["python3", "-m", "pip", "install", "SPARQLWrapper"]