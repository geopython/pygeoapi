FROM docker.elastic.co/elasticsearch/elasticsearch:5.6.8

LABEL maintainer="jorge.dejesus@geocat.net"
ARG DATA_FOLDER=/usr/share/elasticsearch/data

USER root
COPY docker-entrypoint.sh  /docker-entrypoint.sh

COPY add_data.sh /add_data.sh

RUN wget https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh -O bin/wait-for-it.sh
RUN wget https://raw.githubusercontent.com/geopython/pygeoapi/master/tests/data/ne_110m_populated_places_simple.geojson -O /ne_110m_populated_places_simple.geojson  
RUN chmod +x bin/wait-for-it.sh 


RUN echo "xpack.security.enabled: false" >> config/elasticsearch.yml
RUN echo "http.host: 0.0.0.0" >> config/elasticsearch.yml

RUN yum -y install python-setuptools \
	&& easy_install elasticsearch \
	&& yum clean packages

RUN wget https://raw.githubusercontent.com/geopython/pygeoapi/master/tests/load_es_data.py -O /load_es_data.py

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
