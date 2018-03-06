FROM frolvlad/alpine-python3

RUN apk update && apk add --no-cache \
   git \
   python3-dev \ 
   libffi \
   libffi-dev \
   musl-dev \
   gcc \
   openssl-dev \
   g++


RUN git clone https://github.com/geopython/pygeoapi.git

ENV PYGEOAPI_CONFIG=/pygeoapi/local.yml

WORKDIR /pygeoapi
RUN pip3 install -r requirements.txt
RUN pip3 install -r requirements-dev.txt
RUN pip3 install -e .
RUN cp pygeoapi-config.yml local.yml
#export PYGEOAPI_CONFIG=`pwd`/local.yml

ENTRYPOINT ["/usr/bin/python3", "/pygeoapi/pygeoapi/app.py"]

