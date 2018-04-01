import sqlite3
import logging
import os
import geojson
from pygeoapi.provider.base import BaseProvider
from pygeoapi.provider import InvalidProviderError

LOGGER = logging.getLogger(__name__)

class SQLiteProvider(object):
    """Generic provide for SQLITE using sqlite3 module """

    def __init__(self,name, data, id_field):
        
        """
        :param name: provider name
        :param data: file path or URL to data/service assuming that string after :  is table name
        :param id_field: field/property/column of identifier
        :param table: sqlite table
        
        :returns: pygeoapi.providers.base.SQLiteProvider
        """
        BaseProvider.__init__(self, name,data,id_field)
        
        self.data =  data.split(":")[0] #  file:///./tests/data/ne_110m_lakes.sqlite
        self.name = name
        self.id_field = id_field
        self.table = data.split(":")[1] if (len(data.split(":")) > 1) else None
        self.dataDB = None
        
        LOGGER.debug('Setting Sqlite propreties:')
        LOGGER.debug('Data source:{}'.format(self.data))
        LOGGER.debug('Name:{}'.format(self.name))
        LOGGER.debug('ID_field:{}'.format(self.id_field))
        LOGGER.debug('Table:{}'.format(self.table))
        
        
    def __response_feature_collection(self):
        """Assembles GeoJSON output from DB query"""
        
        feature_list = list()
        for row_data in self.dataDB:
            row_data = dict(row_data) #sqlite3.Row is doesnt support pop
            geom = geojson.loads(row_data['AsGeoJSON(geometry)'])
            del row_data['AsGeoJSON(geometry)']
            feature = geojson.Feature(geometry=geom, properties=row_data)
            feature_list.append(feature)
        
        feature_collection = geojson.FeatureCollection(feature_list)
        
        return feature_collection
    
    def __response_feature_hits(self,hits):
        """Assembles GeoJSON/Feature number"""
        feature_collection = geojson.FeatureCollection([])
        feature_collection['numberMatched'] = str(hits)
        return feature_collection

    def __load(self):
        
        """
        Private method for loading spatiallite, get the table structure and dump geometry
        """
        
        if (os.path.exists(self.data)):
            conn = sqlite3.connect(self.data)
        else:
            raise InvalidProviderError

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT load_extension('mod_spatialite')")
        cursor.execute("PRAGMA table_info({})".format(self.table))
           
        result = cursor.fetchall()
        try:        
            #TODO: Better exceptions declaring InvalidProviderError as Parent class
            assert len(result), "Table not found"
            assert len([item for item in result if item['pk'] == 1]), "Primary key not found"
            assert len([item for item in result if self.id_field in item]), "id_field not present"
            assert len([item for item in result if 'GEOMETRY' in item]), "GEOMETRY column not found"
            
        except InvalidProviderError as error:
            raise

        self.columns = [item[1] for item in result if item[1] != 'GEOMETRY']
        self.columns = ",".join(self.columns)+",AsGeoJSON(geometry)"
        #data = cursor.execute('select * from {};'.format(self.table))
        return cursor


    def query(self,startindex=0, limit=10, resulttype='results'):
        """
        Query Sqlite for all the content. 
        e,g: http://localhost:5000/collections/countries/items?limit=1&type=results
        
        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results) 

        :returns: dict of 0..n GeoJSON features
        """
        
        cursor = self.__load() 
        
        if resulttype == 'hits':
            res = cursor.execute("select count(*) as hits from {};".format(self.table))
            hits = res.fetchone()["hits"]
            return self.__response_feature_hits(hits)
        
        
        end_index = startindex+limit
        #http://localhost:5000/collections/countries/items/?startindex=10 Not working
        
        self.dataDB = cursor.execute('select {} from {} where rowid >= {} and rowid <={};'.format(self.columns,self.table,startindex,end_index)) # SQL injection
        
        feature_collection = self.__response_feature_collection()
        return feature_collection
        
        
    def get(self, identifier):
        """
        Query the provider for a specific feature id e.g: /collections/countries/items/1

        :param identifier: feature id
        
        :returns: dict of single GeoJSON feature
        """
	    
        cursor = self.__load()
        self.dataDB = cursor.execute('select {} from {} where {}=={};'.format(self.columns,self.table,self.id_field,identifier)) # SQL injection
        
        feature_collection = self.__response_feature_collection()
        return feature_collection
        

    def __repr__(self):
        return '<SQliteProvider> {}'.format(self.data)

