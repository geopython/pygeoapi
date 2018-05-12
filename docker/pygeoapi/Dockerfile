FROM alpine:edge

LABEL maintainer="jorge.dejesus@geocat.net"

ENV GITHUB https://github.com/geopython/pygeoapi.git
ENV PYGEOAPI_CONFIG /pygeoapi/local.config.yml
ENV PYGEOAPI_OPENAPI /pygeoapi/openapi.yml

ARG FREEXL=freexl-1.0.5.tar.gz
ARG LIBSPATIALITE=libspatialite-4.3.0a.tar.gz

RUN echo "@edge-testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories

RUN apk update && apk add --no-cache \
   git \
   python3-dev \ 
   libffi \
   libffi-dev \
   musl-dev \
   gcc       \
   openssl-dev \
   g++ \
   make \
   sqlite-dev \
   libxml2-dev \
   "proj4-dev@edge-testing" \
   "geos-dev@edge-testing"
 
RUN wget "http://www.gaia-gis.it/gaia-sins/${FREEXL}" && \
          tar zxvf "${FREEXL}" && cd "${FREEXL%.*.*}" $ && \
           ./configure && make -j 4 && make install
RUN ldconfig /usr/local/lib 
RUN wget "http://www.gaia-gis.it/gaia-sins/${LIBSPATIALITE}" && \ 
           tar zxvf "${LIBSPATIALITE}" && cd "${LIBSPATIALITE%.*.*}" && \ 
           ./configure && make -j 4 && make install
RUN ldconfig /usr/local/lib
#RUN git clone -b docker ${GITHUB}
RUN git clone $GITHUB

COPY entrypoint.sh /entrypoint.sh

WORKDIR /pygeoapi
RUN pip3 install -r requirements.txt
RUN pip3 install -r requirements-dev.txt
RUN pip3 install -e .

COPY docker.config.yml local.config.yml

ENTRYPOINT ["/entrypoint.sh"]

#Run using
#docker run -p5000:5000 pygeoapi:latest
