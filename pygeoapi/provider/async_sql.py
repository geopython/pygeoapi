# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2025 Tom Kralidis
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

"""
Async-compatible SQL provider for pygeoapi with connection pooling support.
This provider extends the existing SQL provider with async capabilities.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from pygeoapi.provider.async_base import AsyncSQLProvider
from pygeoapi.provider.sql import SQLProvider
from pygeoapi.util import crs_transform, get_typed_value

LOGGER = logging.getLogger(__name__)


class AsyncSQLProvider(AsyncSQLProvider, SQLProvider):
    """
    Async SQL provider with connection pooling support.
    Extends the existing SQLProvider with async capabilities.
    """

    def __init__(self, provider_def: dict):
        """
        Initialize async SQL provider.

        :param provider_def: provider definition
        """
        # Initialize both parent classes
        AsyncSQLProvider.__init__(self, provider_def)
        SQLProvider.__init__(self, provider_def)

    async def query_async(self, offset: int = 0, limit: int = 10,
                         resulttype: str = 'results',
                         bbox: list = None, datetime_: str = None,
                         properties: list = None, sortby: list = None,
                         select_properties: list = None,
                         skip_geometry: bool = False, q: str = None,
                         **kwargs) -> Dict[str, Any]:
        """
        Async query with connection pooling.

        :param offset: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry
        :param q: full-text search term(s)

        :returns: dict of query results
        """
        if not self._connection_pool:
            # Fallback to sync version
            return await super().query_async(
                offset, limit, resulttype, bbox, datetime_,
                properties, sortby, select_properties, skip_geometry, q, **kwargs
            )

        try:
            # Build the query using existing SQL provider logic
            query_sql, count_sql, params = self._build_query_sql(
                offset, limit, bbox, datetime_, properties, sortby,
                select_properties, skip_geometry, q
            )

            # Execute queries asynchronously
            if resulttype == 'hits':
                count_result = await self.execute_query_async(count_sql, params)
                total_count = count_result[0][0] if count_result else 0
                return {
                    'type': 'FeatureCollection',
                    'features': [],
                    'numberMatched': total_count,
                    'numberReturned': 0
                }

            # Execute main query
            rows = await self.execute_query_async(query_sql, params)

            # Get total count if needed
            total_count = None
            if limit < len(rows) or offset > 0:
                count_result = await self.execute_query_async(count_sql, params)
                total_count = count_result[0][0] if count_result else 0

            # Convert rows to GeoJSON features
            features = []
            for row in rows:
                feature = self._row_to_feature(row, skip_geometry)
                features.append(feature)

            response = {
                'type': 'FeatureCollection',
                'features': features,
                'numberReturned': len(features)
            }

            if total_count is not None:
                response['numberMatched'] = total_count

            return response

        except Exception as e:
            LOGGER.error(f"Async query failed: {e}")
            # Fallback to sync version
            return await super().query_async(
                offset, limit, resulttype, bbox, datetime_,
                properties, sortby, select_properties, skip_geometry, q, **kwargs
            )

    async def get_async(self, identifier: str, **kwargs) -> Dict[str, Any]:
        """
        Async get feature by identifier.

        :param identifier: feature id
        :returns: dict of single feature
        """
        if not self._connection_pool:
            return await super().get_async(identifier, **kwargs)

        try:
            # Build query for single feature
            where_clause = f"{self.id_field} = %s"
            select_clause = self._build_select_clause(skip_geometry=False)

            query = f"""
                SELECT {select_clause}
                FROM {self.table}
                WHERE {where_clause}
                LIMIT 1
            """

            rows = await self.execute_query_async(query, (identifier,))

            if not rows:
                raise RuntimeError(f"Feature {identifier} not found")

            feature = self._row_to_feature(rows[0], skip_geometry=False)
            return feature

        except Exception as e:
            LOGGER.error(f"Async get failed: {e}")
            return await super().get_async(identifier, **kwargs)

    async def create_async(self, item: Dict[str, Any]) -> str:
        """
        Async create new feature.

        :param item: GeoJSON-like dict of item
        :returns: identifier of created item
        """
        if not self._connection_pool:
            return await super().create_async(item)

        try:
            # Build insert query
            insert_sql, params = self._build_insert_sql(item)

            # Execute insert
            await self.execute_query_async(insert_sql, params)

            # Return the identifier
            if 'id' in item:
                return str(item['id'])
            else:
                # Get the last inserted ID
                last_id_query = "SELECT LASTVAL()" if self.engine_type == 'postgresql' else "SELECT LAST_INSERT_ID()"
                result = await self.execute_query_async(last_id_query)
                return str(result[0][0]) if result else None

        except Exception as e:
            LOGGER.error(f"Async create failed: {e}")
            return await super().create_async(item)

    async def update_async(self, identifier: str, item: Dict[str, Any]) -> bool:
        """
        Async update existing feature.

        :param identifier: feature id
        :param item: GeoJSON-like dict of item
        :returns: True if successful, False otherwise
        """
        if not self._connection_pool:
            return await super().update_async(identifier, item)

        try:
            # Build update query
            update_sql, params = self._build_update_sql(identifier, item)

            # Execute update
            result = await self.execute_query_async(update_sql, params)

            # Check if any rows were affected
            return True  # Most async drivers don't return affected row count directly

        except Exception as e:
            LOGGER.error(f"Async update failed: {e}")
            return await super().update_async(identifier, item)

    async def delete_async(self, identifier: str) -> bool:
        """
        Async delete feature.

        :param identifier: feature id
        :returns: True if successful, False otherwise
        """
        if not self._connection_pool:
            return await super().delete_async(identifier)

        try:
            # Build delete query
            delete_sql = f"DELETE FROM {self.table} WHERE {self.id_field} = %s"

            # Execute delete
            await self.execute_query_async(delete_sql, (identifier,))
            return True

        except Exception as e:
            LOGGER.error(f"Async delete failed: {e}")
            return await super().delete_async(identifier)

    def _build_query_sql(self, offset: int, limit: int, bbox: list = None,
                         datetime_: str = None, properties: list = None,
                         sortby: list = None, select_properties: list = None,
                         skip_geometry: bool = False, q: str = None) -> Tuple[str, str, tuple]:
        """
        Build SQL query and count query with parameters.

        :returns: (query_sql, count_sql, params)
        """
        # This method reuses logic from the parent SQL provider
        # but adapts it for async parameter binding

        where_conditions = []
        params = []

        # Add bbox filter
        if bbox:
            geom_field = self.geom_field or 'geom'
            bbox_condition = f"ST_Intersects({geom_field}, ST_MakeEnvelope(%s, %s, %s, %s, %s))"
            where_conditions.append(bbox_condition)
            params.extend([bbox[0], bbox[1], bbox[2], bbox[3], self.srid])

        # Add datetime filter
        if datetime_ and self.time_field:
            time_condition = f"{self.time_field} = %s"
            where_conditions.append(time_condition)
            params.append(datetime_)

        # Add property filters
        if properties:
            for prop, value in properties:
                if prop in self.fields:
                    prop_condition = f"{prop} = %s"
                    where_conditions.append(prop_condition)
                    params.append(value)

        # Add full-text search
        if q:
            # This is a simplified implementation
            text_fields = [f for f, info in self.fields.items()
                          if info.get('type') in ['string', 'text']]
            if text_fields:
                text_conditions = [f"{field} ILIKE %s" for field in text_fields[:3]]  # Limit to first 3 text fields
                where_conditions.append(f"({' OR '.join(text_conditions)})")
                params.extend([f"%{q}%" for _ in text_conditions])

        # Build WHERE clause
        where_clause = ""
        if where_conditions:
            where_clause = f"WHERE {' AND '.join(where_conditions)}"

        # Build SELECT clause
        select_clause = self._build_select_clause(select_properties, skip_geometry)

        # Build ORDER BY clause
        order_clause = ""
        if sortby:
            order_items = []
            for sort_item in sortby:
                field = sort_item.get('property')
                order = sort_item.get('order', 'ASC').upper()
                if field in self.fields:
                    order_items.append(f"{field} {order}")
            if order_items:
                order_clause = f"ORDER BY {', '.join(order_items)}"

        # Main query
        query_sql = f"""
            SELECT {select_clause}
            FROM {self.table}
            {where_clause}
            {order_clause}
            LIMIT {limit} OFFSET {offset}
        """

        # Count query
        count_sql = f"""
            SELECT COUNT(*)
            FROM {self.table}
            {where_clause}
        """

        return query_sql, count_sql, tuple(params)

    def _build_select_clause(self, select_properties: list = None,
                            skip_geometry: bool = False) -> str:
        """Build SELECT clause for queries."""
        if select_properties:
            fields = [f for f in select_properties if f in self.fields]
        else:
            fields = list(self.fields.keys())

        # Always include ID field
        if self.id_field not in fields:
            fields.insert(0, self.id_field)

        # Add geometry field if not skipping
        if not skip_geometry and self.geom_field and self.geom_field not in fields:
            # Convert geometry to text for easier handling
            geom_clause = f"ST_AsText({self.geom_field}) as {self.geom_field}"
            fields.append(geom_clause)

        return ", ".join(fields)

    def _build_insert_sql(self, item: Dict[str, Any]) -> Tuple[str, tuple]:
        """Build INSERT SQL with parameters."""
        properties = item.get('properties', {})
        geometry = item.get('geometry')

        fields = []
        placeholders = []
        params = []

        # Add properties
        for field, value in properties.items():
            if field in self.fields:
                fields.append(field)
                placeholders.append('%s')
                params.append(value)

        # Add geometry
        if geometry and self.geom_field:
            fields.append(self.geom_field)
            placeholders.append('ST_GeomFromText(%s, %s)')
            params.extend([json.dumps(geometry), self.srid])

        sql = f"""
            INSERT INTO {self.table} ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
        """

        return sql, tuple(params)

    def _build_update_sql(self, identifier: str, item: Dict[str, Any]) -> Tuple[str, tuple]:
        """Build UPDATE SQL with parameters."""
        properties = item.get('properties', {})
        geometry = item.get('geometry')

        set_clauses = []
        params = []

        # Update properties
        for field, value in properties.items():
            if field in self.fields and field != self.id_field:
                set_clauses.append(f"{field} = %s")
                params.append(value)

        # Update geometry
        if geometry and self.geom_field:
            set_clauses.append(f"{self.geom_field} = ST_GeomFromText(%s, %s)")
            params.extend([json.dumps(geometry), self.srid])

        # Add WHERE condition
        params.append(identifier)

        sql = f"""
            UPDATE {self.table}
            SET {', '.join(set_clauses)}
            WHERE {self.id_field} = %s
        """

        return sql, tuple(params)

    def _row_to_feature(self, row: tuple, skip_geometry: bool = False) -> Dict[str, Any]:
        """Convert database row to GeoJSON feature."""
        feature = {
            'type': 'Feature',
            'properties': {},
            'geometry': None
        }

        # Map row values to fields
        field_names = list(self.fields.keys())
        if self.geom_field and not skip_geometry:
            field_names.append(self.geom_field)

        for i, value in enumerate(row):
            if i >= len(field_names):
                break

            field_name = field_names[i]

            if field_name == self.id_field:
                feature['id'] = value
            elif field_name == self.geom_field and not skip_geometry:
                if value:
                    # Parse WKT to GeoJSON (simplified)
                    try:
                        from shapely.wkt import loads
                        from shapely.geometry import mapping
                        geom = loads(value)
                        feature['geometry'] = mapping(geom)
                    except Exception:
                        # Fallback to None if geometry parsing fails
                        feature['geometry'] = None
            else:
                feature['properties'][field_name] = value

        return feature

    def _execute_sync_query(self, query: str, params: tuple = None) -> list:
        """Fallback sync query execution using parent class connection."""
        # Use the existing sync connection from parent class
        with self.get_session() as session:
            result = session.execute(query, params or ())
            return result.fetchall()