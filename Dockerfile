# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Just van den Broecke <justb4@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Angelos Tzotsos <gcpp.kalxas@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
# Copyright (c) 2019 Just van den Broecke
# Copyright (c) 2020 Francesco Bartoli
# Copyright (c) 2021 Angelos Tzotsos
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

FROM ubuntu:22.04

LABEL maintainer="Just van den Broecke <justb4@gmail.com>"

# Docker file for full geoapi server with libs/packages for all providers.
# Server runs with gunicorn. You can override ENV settings.
# Defaults:
# SCRIPT_NAME=/
# CONTAINER_NAME=pygeoapi
# CONTAINER_HOST=0.0.0.0
# CONTAINER_PORT=80
# WSGI_WORKERS=4
# WSGI_WORKER_TIMEOUT=6000
# WSGI_WORKER_CLASS=gevent

# Calls entrypoint.sh to run. Inspect it for options.
# Contains some test data. Also allows you to verify by running all unit tests.
# Simply run: docker run -it geopython/pygeoapi test
# Override the default config file /pygeoapi/local.config.yml
# via Docker Volume mapping or within a docker-compose.yml file. See example at
# https://github.com/geopython/demo.pygeoapi.io/tree/master/services/pygeoapi

# Build arguments
# add "--build-arg BUILD_DEV_IMAGE=true" to Docker build command when building with test/doc tools

# ARGS
ARG TZ="Etc/UTC"
ARG LANG="en_US.UTF-8"
ARG BUILD_DEV_IMAGE="false"
ARG ADD_DEB_PACKAGES="\
    python3-dask \
    python3-elasticsearch \
    python3-fiona \
    python3-gdal \
    python3-netcdf4 \
    python3-pandas \
    python3-psycopg2 \
    python3-pymongo \
    python3-pyproj \
    python3-rasterio \
    python3-scipy \
    python3-tinydb \
    python3-xarray \
    python3-zarr \
    python3-mapscript \
    "

# ENV settings
ENV TZ=${TZ} \
    LANG=${LANG} \
    DEBIAN_FRONTEND="noninteractive" \
    DEB_BUILD_DEPS="\
      gcc-aarch64-linux-gnu \
      curl \
      python3-dev \
      software-properties-common \
      unzip" \
    DEB_PACKAGES="\
      gunicorn \
      libsqlite3-mod-spatialite \
      locales \
      locales-all \
      python3-dateutil \
      python3-distutils \
      python3-flask \
      python3-flask-cors \
      python3-gevent \
      python3-greenlet \
      python3-pip \
      python3-setuptools \
      python3-shapely \
      python3-tz \
      python3-unicodecsv \
      python3-wheel \
      python3-yaml \
      ${ADD_DEB_PACKAGES}"

# Install operating system dependencies
RUN \
    apt-get update -y \
    && apt-get upgrade -y \
    && apt-get install -y --fix-missing --no-install-recommends ${DEB_BUILD_DEPS}  \
    && add-apt-repository ppa:ubuntugis/ubuntugis-unstable \
    && apt-get --no-install-recommends install -y ${DEB_PACKAGES} \
    && update-locale LANG=${LANG} \
    && echo "For ${TZ} date=$(date)" && echo "Locale=$(locale)"

# OGC schemas local setup
WORKDIR /schemas.opengis.net
RUN \
    curl -O http://schemas.opengis.net/SCHEMAS_OPENGIS_NET.zip \
    && unzip ./SCHEMAS_OPENGIS_NET.zip "ogcapi/*" -d /schemas.opengis.net \
    && rm -f ./SCHEMAS_OPENGIS_NET.zip

WORKDIR /pygeoapi
RUN mkdir -p /pygeoapi/pygeoapi
# Add files required for pip/setuptools
ADD requirements*.txt setup.py README.md /pygeoapi/
ADD pygeoapi/__init__.py /pygeoapi/pygeoapi/

RUN \
    # Install pygeoapi
    # Optionally add development/test/doc packages
    if [ "$BUILD_DEV_IMAGE" = "true" ] ; then pip3 install -r requirements-dev.txt; fi \
    # Install pygeoapi providers
    && pip3 install -r requirements-provider.txt \
    # Install pygeoapi
    && pip3 install -e .

RUN \
    # Cleanup TODO: remove unused Locales and TZs
    apt-get remove --purge -y ${DEB_BUILD_DEPS} \
    && apt autoremove -y  \
    && rm -rf /var/lib/apt/lists/*

ADD . /pygeoapi

COPY ./docker/default.config.yml /pygeoapi/local.config.yml
COPY ./docker/entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
