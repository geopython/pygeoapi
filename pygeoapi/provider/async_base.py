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
Async-compatible base classes for pygeoapi providers.
These classes provide async database operations and connection pooling support.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, Union

from pygeoapi.provider.base import BaseProvider, ProviderConnectionError

LOGGER = logging.getLogger(__name__)


class AsyncBaseProvider(BaseProvider, ABC):
    """
    Async-compatible base provider class that supports connection pooling
    and non-blocking database operations.
    """

    def __init__(self, provider_def: dict):
        """
        Initialize async provider.

        :param provider_def: provider definition
        """
        super().__init__(provider_def)
        self._connection_pool = None
        self._resource_name = provider_def.get('resource_name')

    def set_connection_pool(self, pool: Any):
        """
        Set the connection pool for this provider instance.

        :param pool: Database connection pool
        """
        self._connection_pool = pool

    async def query_async(self, offset: int = 0, limit: int = 10,
                         resulttype: str = 'results',
                         bbox: list = None, datetime_: str = None,
                         properties: list = None, sortby: list = None,
                         select_properties: list = None,
                         skip_geometry: bool = False, q: str = None,
                         **kwargs) -> Dict[str, Any]:
        """
        Async version of the query method.

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
        # Default implementation calls sync version in executor
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.query, offset, limit, resulttype, bbox,
            datetime_, properties, sortby, select_properties,
            skip_geometry, q, **kwargs
        )

    async def get_async(self, identifier: str, **kwargs) -> Dict[str, Any]:
        """
        Async version of the get method.

        :param identifier: feature id
        :returns: dict of single feature
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get, identifier, **kwargs)

    async def create_async(self, item: Dict[str, Any]) -> str:
        """
        Async version of the create method.

        :param item: GeoJSON-like dict of item
        :returns: identifier of created item
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.create, item)

    async def update_async(self, identifier: str, item: Dict[str, Any]) -> bool:
        """
        Async version of the update method.

        :param identifier: feature id
        :param item: GeoJSON-like dict of item
        :returns: True if successful, False otherwise
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.update, identifier, item)

    async def delete_async(self, identifier: str) -> bool:
        """
        Async version of the delete method.

        :param identifier: feature id
        :returns: True if successful, False otherwise
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.delete, identifier)


class AsyncSQLProvider(AsyncBaseProvider):
    """
    Async SQL provider base class with connection pooling support.
    """

    def __init__(self, provider_def: dict):
        super().__init__(provider_def)
        self._pool_type = 'sql'

    async def _get_connection(self):
        """Get a connection from the pool."""
        if not self._connection_pool:
            raise ProviderConnectionError("No connection pool available")

        try:
            # Handle different pool types
            if hasattr(self._connection_pool, 'acquire'):
                # asyncpg style
                return await self._connection_pool.acquire()
            elif hasattr(self._connection_pool, 'get_conn'):
                # aiomysql style
                return await self._connection_pool.get_conn()
            else:
                raise ProviderConnectionError("Unsupported connection pool type")
        except Exception as e:
            raise ProviderConnectionError(f"Failed to acquire connection: {e}")

    async def _release_connection(self, connection):
        """Release a connection back to the pool."""
        try:
            if hasattr(self._connection_pool, 'release'):
                # asyncpg style
                await self._connection_pool.release(connection)
            elif hasattr(connection, 'close'):
                # aiomysql style
                connection.close()
        except Exception as e:
            LOGGER.warning(f"Error releasing connection: {e}")

    async def execute_query_async(self, query: str, params: tuple = None) -> list:
        """
        Execute a query asynchronously using the connection pool.

        :param query: SQL query string
        :param params: Query parameters
        :returns: Query results
        """
        if not self._connection_pool:
            # Fallback to sync execution
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._execute_sync_query, query, params)

        connection = await self._get_connection()
        try:
            if hasattr(connection, 'fetch'):
                # asyncpg style
                if params:
                    return await connection.fetch(query, *params)
                else:
                    return await connection.fetch(query)
            elif hasattr(connection, 'execute'):
                # aiomysql style
                cursor = await connection.cursor()
                try:
                    await cursor.execute(query, params)
                    return await cursor.fetchall()
                finally:
                    await cursor.close()
            else:
                raise ProviderConnectionError("Unsupported connection type")
        finally:
            await self._release_connection(connection)

    def _execute_sync_query(self, query: str, params: tuple = None) -> list:
        """Fallback sync query execution."""
        # This should be implemented by subclasses
        raise NotImplementedError("Sync query execution not implemented")


class AsyncMongoProvider(AsyncBaseProvider):
    """
    Async MongoDB provider base class with connection pooling support.
    """

    def __init__(self, provider_def: dict):
        super().__init__(provider_def)
        self._pool_type = 'mongo'
        self._database_name = provider_def.get('database')
        self._collection_name = provider_def.get('collection')

    def get_collection(self):
        """Get the MongoDB collection."""
        if not self._connection_pool:
            raise ProviderConnectionError("No MongoDB client available")

        database = self._connection_pool[self._database_name]
        return database[self._collection_name]

    async def find_async(self, filter_dict: dict = None, **kwargs) -> list:
        """
        Async MongoDB find operation.

        :param filter_dict: MongoDB filter dictionary
        :returns: List of documents
        """
        collection = self.get_collection()
        cursor = collection.find(filter_dict or {}, **kwargs)
        return await cursor.to_list(length=None)

    async def find_one_async(self, filter_dict: dict = None, **kwargs) -> dict:
        """
        Async MongoDB find_one operation.

        :param filter_dict: MongoDB filter dictionary
        :returns: Document or None
        """
        collection = self.get_collection()
        return await collection.find_one(filter_dict or {}, **kwargs)

    async def insert_one_async(self, document: dict) -> str:
        """
        Async MongoDB insert_one operation.

        :param document: Document to insert
        :returns: Inserted document ID
        """
        collection = self.get_collection()
        result = await collection.insert_one(document)
        return str(result.inserted_id)

    async def update_one_async(self, filter_dict: dict, update_dict: dict) -> bool:
        """
        Async MongoDB update_one operation.

        :param filter_dict: Filter for document to update
        :param update_dict: Update operations
        :returns: True if successful
        """
        collection = self.get_collection()
        result = await collection.update_one(filter_dict, update_dict)
        return result.modified_count > 0

    async def delete_one_async(self, filter_dict: dict) -> bool:
        """
        Async MongoDB delete_one operation.

        :param filter_dict: Filter for document to delete
        :returns: True if successful
        """
        collection = self.get_collection()
        result = await collection.delete_one(filter_dict)
        return result.deleted_count > 0