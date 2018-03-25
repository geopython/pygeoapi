import sqlite3

import os
from collections import OrderedDict
from pygeoapi.provider.base import BaseProvider
from pygeoapi.provider import InvalidProviderError

class SQLiteProvider(object):
    """Generic provide for """

    def __init__(self, name, data,id_field,table):
        """Provider class for SQLITE"""
        BaseProvider.__init__(self, name,data,id_field)
        #From view we get these arguments
        #p = load_provider(settings['datasets'][dataset]['provider'],
        #                  settings['datasets'][dataset]['data'],
        #                  settings['datasets'][dataset]['id_field'])

        self.data =  self.data #  file:///home/jorge/Projects/pygeoapi/pygeoapi/data/ne_110m_lakes.sqlite
        self.name = name # Sqlite
        self.id_field = id_field
        #self.table = definition["table"]
        #self.id_field = definition["id_field"]
        self.table = table


    def _load(self):
        if (os.path.exists(self.data)):
            conn = sqlite3.connect(self.data)
        else:
            raise InvalidProviderError
            #assert isinstance(conn, sqlite3.Connection)
	#Checkk if we have content (asset table and assert id)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # table names cannot be parametrized.
        cursor.execute("SELECT load_extension('mod_spatialite')")
        cursor.execute("PRAGMA table_info({})".format(self.table))
           

	#[(0, 'OGC_FID', 'INTEGER', 0, None, 1), (1, 'GEOMETRY', 'BLOB', 0, None, 0), (2, 'scalerank', 'INTEGER', 0, None, 0), (3, 'name', 'VARCHAR(255)', 0, None, 0), (4, 'name_alt', 'VARCHAR(255)', 0, None, 0), (5, 'admin', 'VARCHAR(255)', 0, None, 0), (6, 'featureclass', 'VARCHAR(255)', 0, None, 0)]


        result = cursor.fetchall()
        try:
            assert len(result) # Check that we have a table
            assert len([item for item in result if self.id_field in item]) # check id the id_field is present
            assert len([item for item in result if 'GEOMETRY' in item])
        except:
            raise InvalidProviderError

        self.columns = [item[1] for item in result if item[1] != 'GEOMETRY']
        #data = cursor.execute('select * from {};'.format(self.table))
        return cursor

        


    def query(self):
        """
        query the provider
	Assuming results

        :returns: dict of 0..n GeoJSON features
        """
        cursor = self._load() # sqlite connection 
        columns = ",".join(self.columns)+",AsGeoJSON(geometry)"
	
        dataDB = cursor.execute('select {}  from {};'.format(columns,self.table)) # SQL injection
        for item in dataDB:
            print(dict(item))
		
        


    def get(self, identifier):
        """
        query the provider by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """
	
        raise NotImplementedError()

    def __repr__(self):
        return '<SQliteProvider> {}'.format(self.url)

