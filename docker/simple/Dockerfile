FROM alpine:3.8

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
   curl \
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

#remove elatic search
RUN rm /pygeoapi/pygeoapi/provider/elasticsearch_.py
RUN sed  -i '/pygeoapi.provider.elasticsearch/d' /pygeoapi/pygeoapi/provider/__init__.py

WORKDIR /pygeoapi


RUN pip3 install -r requirements.txt
RUN pip3 install -r requirements-dev.txt
RUN pip3 install -e .

COPY docker.config.yml local.config.yml
COPY run_pygeoapi.sh /run_pygeoapi.sh

ENTRYPOINT ["/run_pygeoapi.sh"]

#Run using:
#docker run -p5000:5000 pygeoapi:latest
#Run using unamed volume:
#docker run -p5000:5000 -v /pygeoapi/tests/data pygeoapi:latest
#Run using named volume:
#docker volume create pygeoapi_volume
#docker run -p5000:5000 -v pygeoapi_volume:/pygeoapi/tests/data pygeoapi:latest
