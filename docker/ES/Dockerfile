
FROM docker.elastic.co/elasticsearch/elasticsearch:5.6.8

<<<<<<< ecf775f8d7177a9720d07dcf03a1a42d75085903
#ARG GDAL_VERSION=2.2.4
#ARG PROCESSOR_N=6

#WORKDIR--> /usr/share/elasticsearch
COPY docker-entrypoint.sh  /docker-entrypoint.sh
COPY wait-for-it.sh bin/wait-for-it.sh
COPY add_data.sh /add_data.sh
#/usr/share/elasticsearch/data
RUN wget https://raw.githubusercontent.com/geopython/pygeoapi/master/tests/data/ne_110m_populated_places_simple.geojson -O /ne_110m_populated_places_simple.geojson  
#RUN chmod +x bin/wait-for-it.sh /docker-entrypoint.sh 
# Cant get the variables to work :( from -e they are visible but is not taking them in
RUN echo "xpack.security.enabled: false" >> config/elasticsearch.yml
RUN echo "http.host: 0.0.0.0" >> config/elasticsearch.yml

#install GDAL to add content to ES
#USER root
#To many packages
#RUN yum -y groupinstall "Development Tools"
#RUN yum -y install wget gcc gcc-c++ flex make

#RUN wget http://download.osgeo.org/gdal/${GDAL_VERSION}/gdal-${GDAL_VERSION}.tar.gz -O /tmp/gdal.tar.gz && \
#	tar xzf /tmp/gdal.tar.gz -C /tmp && \
#	cd /tmp/gdal-${GDAL_VERSION} && \
#     ./configure  --with-geos=yes \
#     && make -j ${PROCESSOR_N} && make install

#Check we have ElasticSearch
#RUN ogrinfo --formats | grep "ElasticSearch"
ARG DATA_FOLDER=/usr/share/elasticsearch/data

COPY docker-entrypoint.sh  /docker-entrypoint.sh
COPY wait-for-it.sh bin/wait-for-it.sh
COPY add_data.sh /add_data.sh

#COPY load_es_data.py /load_es_data.py
#/usr/share/elasticsearch/data
RUN wget https://raw.githubusercontent.com/geopython/pygeoapi/master/tests/data/ne_110m_populated_places_simple.geojson -O $DATA_FOLDER/ne_110m_populated_places_simple.geojson  


RUN echo "xpack.security.enabled: false" >> config/elasticsearch.yml
RUN echo "http.host: 0.0.0.0" >> config/elasticsearch.yml

USER root
RUN yum -y install python-setuptools \
	&& easy_install elasticsearch \
	&& yum clean packages

USER elasticsearch
CMD ["/usr/share/elasticsearch/bin/elasticsearch"]

ENTRYPOINT ["/docker-entrypoint.sh"]
# we need to run this on host 
#sudo sysctl -w vm.max_map_count=262144
#check indices
#http://localhost:9200/_cat/indices?v
#check spatial data
#http://localhost:9200/ne_110m_populated_places_simple/
#This docker compose was inspired on:
#https://discuss.elastic.co/t/best-practice-for-creating-an-index-when-an-es-docker-container-starts/126651 
#docker run -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" es:latest
