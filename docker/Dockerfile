FROM frolvlad/alpine-python3

ENV PYGEOAPI_CONFIG=/pygeoapi/local.config.yml
ENV PYGEOAPI_OPENAPI=/pygeoapi/openapi.yml
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


WORKDIR /pygeoapi
RUN pip3 install -r requirements.txt
RUN pip3 install -r requirements-dev.txt
RUN pip3 install -e .
RUN cp pygeoapi-config.yml local.config.yml
RUN pygeoapi generate_openapi_document -c local.config.yml > openapi.yml
#export PYGEOAPI_CONFIG=`pwd`/local.yml
ENTRYPOINT ["pygeoapi","serve"]
#ENTRYPOINT ["/usr/bin/python3", "/pygeoapi/pygeoapi/app.py"]

