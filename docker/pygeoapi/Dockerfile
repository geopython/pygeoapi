FROM alpine:edge

ENV GITHUB https://github.com/GeoCat/pygeoapi.git
ENV PYGEOAPI_CONFIG /pygeoapi/local.config.yml
ENV PYGEOAPI_OPENAPI /pygeoapi/openapi.yml

ARG FREEXL=freexl-1.0.5.tar.gz
ARG LIBSPATIALITE=libspatialite-4.3.0a.tar.gz
#RUN echo "@edge http://nl.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories
RUN echo "@edge-testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories
#RUN apk update


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
 
RUN wget "http://www.gaia-gis.it/gaia-sins/${LIBSPATIALITE}" && \ 
           tar zxvf "${LIBSPATIALITE}" && cd "${LIBSPATIALITE%.*.*}" && \ 
           ./configure && make -j 4 && make install

  
RUN git clone -b docker ${GITHUB}

WORKDIR /pygeoapi
RUN pip3 install -r requirements.txt
RUN pip3 install -r requirements-dev.txt
RUN pip3 install -e .
RUN cp pygeoapi-config.yml local.config.yml
#export PYGEOAPI_CONFIG=`pwd`/local.yml
RUN pygeoapi generate_openapi_document -c local.config.yml > openapi.yml

ENTRYPOINT ["pygeoapi", "serve"]

#docker run -p5000:5000 pygeoapi:latest
