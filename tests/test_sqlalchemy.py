"""Testing geoalchmey with sqlite
https://www.pythoncentral.io/sqlalchemy-faqs/
https://www.blog.pythonlibrary.org/2010/09/10/sqlalchemy-connecting-to-pre-existing-databases/
https://gist.github.com/brambow/889aca48831e189a62eec5a70067bf8e
https://github.com/geoalchemy/geoalchemy/blob/master/doc/usagenotes.rst  #sqlite notes
Successfully installed SQLAlchemy-1.2.5 geoalchemy-0.7.2
Code from:
https://gist.github.com/Sleepingwell/7445312
install:
apt install libsqlite3-mod-spatialite
"""

class ProviderData(object):
    pass
 
db_path = "./data/ne_110m_lakes.sqlite"
table_name = "v_ne_110m_lakes"

from sqlalchemy import event, create_engine, MetaData, Table,Integer,Column,Unicode,BLOB
from sqlalchemy.orm import sessionmaker,mapper
engine = create_engine('sqlite:///{}'.format(db_path),echo=True)

# this enables the extension on each connection
@event.listens_for(engine, "connect")
def connect(dbapi_connection, connection_rec):
    dbapi_connection.enable_load_extension(True)
    dbapi_connection.execute("SELECT load_extension('mod_spatialite')")


metadata = MetaData(engine,reflect=True)
metadata.reflect(bind=engine)

session = sessionmaker(bind=engine)()

provider_table = Table(table_name, metadata,Column('GEOMETRY', BLOB), autoload=True,extend_existing=True)
mapper(ProviderData, provider_table)
#mapper(ProviderData, provider_table,exclude_properties={"GEOMETRY"})

query=session.query(ProviderData)
for row in query.all():
    print(row.GEOMETRY)

