"""
Proof-of-concept script demonstrating pygeofilter and sqlalchemy
to run a CQL query.

Set up test database with:

```
docker run --name "postgis" \
 -v postgres_data:/var/lib/postgresql -p 5432:5432 \
 -e ALLOW_IP_RANGE=0.0.0.0/0 \
 -e POSTGRES_USER=postgres \
 -e POSTGRES_PASS=postgres \
 -e POSTGRES_DBNAME=test \
 -d -t kartoza/postgis

gunzip < tests/data/hotosm_bdi_waterways.sql.gz | \
    PGPASSWORD=postgres psql -U postgres -h 127.0.0.1 -p 5432 test
```

Run with: python pygeofilter_sqlalchemy_demo.py
"""
# coding: utf-8
from pprint import pprint

from sqlalchemy import create_engine, MetaData, PrimaryKeyConstraint
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry  # noqa - this isn't used explicitly but is needed to process Geometry columns
from pygeofilter.parsers.ecql import parse
from pygeofilter.backends.sqlalchemy.evaluate import to_filter

SCHEMAS = ['osm', 'public']
TABLE = 'hotosm_bdi_waterways'
ID_FIELD = 'osm_id'
GEOM_FIELD = 'geom'
CQL_QUERY = "osm_id BETWEEN 3e6 AND 3e7" # Add to query method
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
connection_string = 'postgresql://postgres:postgres@localhost:5432/test'
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
TableModel = getattr(Base.classes, TABLE)

# Prepare CQL requirements
field_mapping = {column_name: getattr(TableModel, column_name)
                 for column_name in TableModel.__table__.columns.keys()}
filters = to_filter(ast, field_mapping)

# Create session to run a query
Session = sessionmaker(bind=engine)
session = Session()

print(f"Querying {TABLE}: {CQL_QUERY}")
q = session.query(TableModel).filter(filters)
for row in q:
    row_dict = row.__dict__
    row_dict.pop('_sa_instance_state')  # Internal SQLAlchemy metadata
    geom = row_dict.pop(GEOM_FIELD)
    pprint(row_dict)
