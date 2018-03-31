import sqlite3

import os
import geojson
from pygeoapi.provider.base import BaseProvider
from pygeoapi.provider import InvalidProviderError



class SQLiteProvider(object):
    """Generic provide for SQLITE using sqlite3 module """

    def __init__(self,name, data, id_field,table):
        
        """
        :param name: provider name
        :param data: file path or URL to data/service
        :param id_field: field/property/column of identifier
        :param table: sqlite table
        
        :returns: pygeoapi.providers.base.SQLiteProvider
        """
        BaseProvider.__init__(self, name,data,id_field)
        #From view we get these arguments
        #p = load_provider(settings['datasets'][dataset]['provider'],
        #                  settings['datasets'][dataset]['data'],
        #                  settings['datasets'][dataset]['id_field'])

        self.data =  self.data #  file:///./tests/data/ne_110m_lakes.sqlite
    
        self.name = name
        self.id_field = id_field
        self.table = table

    def dict_factory(cursor, row):
        """
        Function to return sqlite3 row as a dictionary
        :param cursor: sqlite3.Cursor
        :param row: sqlite3.Row
        
        :returns: dict
        
        """ 
        
        d = {} 
        for idx, col in enumerate(cursor.description): 
            d[col[0]] = row[idx] 
        return d 

    def _load(self):
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
           
            #TODO: Better exceptions
            assert len(result), "Table not found"
            assert len([item for item in result if item['pk'] == 1]), "Primary key not found"
            assert len([item for item in result if self.id_field in item]), "id_field not present"
            assert len([item for item in result if 'GEOMETRY' in item]), "GEOMETRY column not found"
            
        except InvalidProviderError as error:
            raise

        self.columns = [item[1] for item in result if item[1] != 'GEOMETRY']
        #data = cursor.execute('select * from {};'.format(self.table))
        return cursor


    def query(self):
        """
        Query the provider for all the content 

        :returns: dict of 0..n GeoJSON features
        """
        cursor = self._load() # sqlite connection 
        columns = ",".join(self.columns)+",AsGeoJSON(geometry)"
	
        dataDB = cursor.execute('select {} from {};'.format(columns,self.table)) # SQL injection
        
        feature_list = list()
        for row_data in dataDB:
            row_data = dict(row_data) #sqlite3.Row is doesnt support pop
            geom = geojson.loads(row_data['AsGeoJSON(geometry)'])
            del row_data['AsGeoJSON(geometry)']
            feature = geojson.Feature(geometry=geom, properties=row_data)
            feature_list.append(feature)
        
        
        feature_collection = geojson.FeatureCollection(feature_list)
        return feature_collection
		
        
    def get(self, identifier):
        """
        query the provider by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """
	
        raise NotImplementedError()

    def __repr__(self):
        return '<SQliteProvider> {}'.format(self.url)

