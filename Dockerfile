# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Just van den Broecke <justb4@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Angelos Tzotsos <gcpp.kalxas@gmail.com>
#          Francesco Frassinelli <fraph24@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
# Copyright (c) 2019 Just van den Broecke
# Copyright (c) 2020 Francesco Bartoli
# Copyright (c) 2021 Angelos Tzotsos
# Copyright (c) 2022 Francesco Frassinelli
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

ARG groups="provider gunicorn dev"

FROM ubuntu:jammy AS base
ENV DEBIAN_FRONTEND="noninteractive"
RUN rm -f /etc/apt/apt.conf.d/docker-clean; \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' \
      > /etc/apt/apt.conf.d/keep-cache

FROM base AS common
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
    --mount=type=cache,sharing=locked,target=/var/lib/apt \
      apt-get update && \
      apt-get install -qy --no-install-recommends \
        python3 \
        python3-pip

# Install pdm
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install pdm

FROM base AS schema
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
    --mount=type=cache,sharing=locked,target=/var/lib/apt \
    apt-get update && \
    apt-get install -qy --no-install-recommends \
      curl \
      unzip

# OGC schemas local setup
RUN curl -O http://schemas.opengis.net/SCHEMAS_OPENGIS_NET.zip && \
    unzip ./SCHEMAS_OPENGIS_NET.zip 'ogcapi/*' -d /schemas.opengis.net

FROM common AS build
ARG groups
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
    --mount=type=cache,sharing=locked,target=/var/lib/apt \
      apt-get update && \
      apt-get install -qy --no-install-recommends \
        python3-dev \
        gcc \
        g++ \
        libgdal-dev

WORKDIR /pygeoapi
COPY pyproject.toml pdm.lock ./
RUN --mount=type=cache,target=/root/.cache/pdm \
    pdm install --no-lock --no-self \
      $(for group in $groups; do echo -n "--group $group "; done)

FROM common
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
    --mount=type=cache,sharing=locked,target=/var/lib/apt \
    apt-get update && \
    apt-get install -qy --no-install-recommends \
      libsqlite3-mod-spatialite \
      proj-bin \
      libgdal30

WORKDIR /pygeoapi
COPY --from=schema /schemas.opengis.net /schemas.opengis.net
COPY --from=build /pygeoapi/.venv .venv
COPY ./docker/default.config.yml /pygeoapi/local.config.yml
COPY ./docker/entrypoint.sh /entrypoint.sh
COPY . .
RUN --mount=type=cache,target=/root/.cache/pdm \
    pdm install --no-lock

ENTRYPOINT ["/entrypoint.sh"]
