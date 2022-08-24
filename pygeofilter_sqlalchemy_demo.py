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

from sqlalchemy import create_engine, MetaData, PrimaryKeyConstraint, asc, desc
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry  # noqa - this isn't used explicitly but is needed to process Geometry columns
from pygeofilter.parsers.ecql import parse
from pygeofilter.backends.sqlalchemy.evaluate import to_filter

SCHEMAS = ['osm', 'public']
TABLE = 'hotosm_bdi_waterways'
ID_FIELD = 'osm_id'
GEOM_FIELD = 'foo_geom'
CQL_QUERY = "osm_id BETWEEN 80000000 AND 90000000" # Add to query method
# Later
OFFSET = 20
LIMIT = 20
SORTBY = [{'property': 'waterway', 'order': '-'},
          {'property': 'osm_id', 'order': '+'}]
RESULTTYPE = 'results' # or 'hits' for count only
# Very later
SELECT_PROPERTIES = [] # Subset of columns
SKIP_GEOMETRY = False


# Create a list of order_by clauses
def get_order_by_clauses(sort_by, table_model):
    clauses = []
    for sort_by_dict in sort_by:
        model_column = getattr(table_model, sort_by_dict['property'])
        order_function = asc if sort_by_dict['order'] == '+' else desc
        clauses.append(order_function(model_column))
    return clauses


def query_cql(engine, offset=0, limit=10, resulttype='results',
              bbox=[], sortby=[], select_properties=[], skip_geometry=False,
              cql_ast=None, **kwargs):

    metadata = MetaData(engine)
    metadata.reflect(schema=SCHEMAS[0], views=True)

    # Create SQLAlchemy model from reflected table
    # It is necessary to add the primary key constraint because SQLAlchemy
    # requires it to reflect the table, but a view in a PostgreSQL database does
    # not have a primary key defined.
    sqlalchemy_table_def = metadata.tables[f'{SCHEMAS[0]}.{TABLE}']
    sqlalchemy_table_def.append_constraint(PrimaryKeyConstraint(ID_FIELD))
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


    order_by_clauses = get_order_by_clauses(sortby, TableModel)

    print(f"Querying {TABLE}: {CQL_QUERY}")
    q = session.query(TableModel).filter(filters).order_by(*order_by_clauses).offset(offset).limit(limit)

    result = []
    for row in q:
        row_dict = row.__dict__
        row_dict.pop('_sa_instance_state')  # Internal SQLAlchemy metadata
        result.append(row_dict)

    return result


if __name__ == '__main__':
    # Done in the API
    ast = parse(CQL_QUERY)
    # Connect to database and read tables
    connection_string = 'postgresql://postgres:postgres@localhost:5432/test'
    engine = create_engine(connection_string)
    result = query_cql(engine, offset=OFFSET, limit=LIMIT, sortby=SORTBY, cql_ast=ast)

    pprint(result)
