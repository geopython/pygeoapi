"""
Proof-of-concept script demonstrating pygeofilter and sqlalchemy
to run a CQL query.

Requires environment variable with connection details:
export CONN_STR="postgresql://username:xxxxx@hostname:5432/dbname

Run with: python pygeofiler_sqlalchemy_demo.py
"""
# coding: utf-8
import os

from sqlalchemy import create_engine
from sqlalchemy import MetaData
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import PrimaryKeyConstraint
from geoalchemy2 import Geometry  # noqa - this isn't used explicitly but is needed to process Geometry columns
from pygeofilter.parsers.ecql import parse
from pygeofilter.backends.sqlalchemy.evaluate import to_filter

SCHEMAS = ['published', 'public']
TABLE = 'ql_sen_sensor_location'
ID_COLUMN = 'sensor_loc_id'
CQL_QUERY = "sensor_loc_id BETWEEN 52970 AND 100000" # Add to query method
# Later
OFFSET = 0
LIMIT = 10
# Very later
RESULTTYPE = 'results' # or 'hits' for count only
SELECT_PROPERTIES = [] # Subset of columns
SKIP_GEOMETRY = False

# Done in the API
ast = parse(CQL_QUERY)

# Done in the provider

# Connect to database and read tables
connection_string = os.environ['CONN_STR']
engine = create_engine(connection_string)
metadata = MetaData(engine)
metadata.reflect(schema=SCHEMAS[0], views=True)

# Create SQLAlchemy model from reflected table
# It is necessary to add the primary key constraint because SQLAlchemy
# requires it to reflect the table, but a view in a PostgreSQL database does
# not have a primary key defined.
sqlalchemy_table_def = metadata.tables[f'{SCHEMAS[0]}.{TABLE}']
sqlalchemy_table_def.append_constraint(PrimaryKeyConstraint(ID_COLUMN))
Base = automap_base(metadata=metadata)
Base.prepare()

# TODO: make this generic
TableModel = getattr(Base.classes, TABLE)

# Create session to run a query
Session = sessionmaker(bind=engine)
session = Session()

# Prepare CQL requirements
field_mapping = {column_name: getattr(TableModel, column_name)
                 for column_name in TableModel.__table__.columns.keys()}
filters = to_filter(ast, field_mapping)

# Run the query
print(f"Querying {TABLE}: {CQL_QUERY}")
q = session.query(TableModel).filter(filters)
for row in q:
    print(','.join(str(item) 
                   for item in (row.sensor_loc_id, row.x, row.y, row.site_trans)))
