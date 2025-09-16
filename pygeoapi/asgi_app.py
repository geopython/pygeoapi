# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2025 Tom Kralidis
# Copyright (c) 2025 Francesco Bartoli
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
ASGI application entry point optimized for gunicorn with uvicorn workers.
This module provides async-compatible database connection pooling and
enhanced performance for production deployments.
"""

import asyncio
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from pygeoapi.config import get_config
from pygeoapi.openapi import load_openapi_document
from pygeoapi.starlette_app import APP as STARLETTE_APP
from pygeoapi.util import get_api_rules

LOGGER = logging.getLogger(__name__)

# Global application configuration
CONFIG = get_config()
OPENAPI = load_openapi_document()
API_RULES = get_api_rules(CONFIG)

# Connection pools for async database operations
_connection_pools: Dict[str, Any] = {}


class AsyncConnectionPoolMiddleware(BaseHTTPMiddleware):
    """
    Middleware to manage async database connection pools
    and ensure proper cleanup on application shutdown.
    """

    def __init__(self, app, config: dict):
        super().__init__(app)
        self.config = config
        self._pools_initialized = False

    async def dispatch(self, request: Request, call_next) -> Response:
        """Handle request with connection pool management."""
        if not self._pools_initialized:
            await self._initialize_pools()
            self._pools_initialized = True

        # Attach connection pools to request state for providers
        request.state.connection_pools = _connection_pools

        response = await call_next(request)
        return response

    async def _initialize_pools(self):
        """Initialize async connection pools for database providers."""
        try:
            await _initialize_async_pools(self.config)
            LOGGER.info("Async connection pools initialized successfully")
        except Exception as e:
            LOGGER.error(f"Failed to initialize connection pools: {e}")


async def _initialize_async_pools(config: dict):
    """
    Initialize async connection pools for database providers.

    :param config: pygeoapi configuration dictionary
    """
    global _connection_pools

    # Look for database providers that could benefit from connection pooling
    for resource_name, resource_config in config.get('resources', {}).items():
        providers = resource_config.get('providers', [])

        for provider in providers:
            provider_type = provider.get('type', '')
            provider_name = provider.get('name', '')

            # Initialize pools for SQL-based providers
            if provider_name in ['PostgreSQL', 'MySQL', 'Oracle']:
                await _init_sql_pool(resource_name, provider)
            elif provider_name == 'MongoDB':
                await _init_mongo_pool(resource_name, provider)
            elif provider_name == 'Elasticsearch':
                await _init_elasticsearch_pool(resource_name, provider)


async def _init_sql_pool(resource_name: str, provider_config: dict):
    """Initialize async SQL connection pool."""
    try:
        # Check if asyncpg or aiomysql is available for async SQL operations
        pool_key = f"sql_{resource_name}"

        connection_string = provider_config.get('data', {})
        if isinstance(connection_string, dict):
            # Extract connection parameters
            host = connection_string.get('host', 'localhost')
            port = connection_string.get('port')
            database = connection_string.get('database')
            user = connection_string.get('user')
            password = connection_string.get('password')

            if provider_config.get('name') == 'PostgreSQL':
                try:
                    import asyncpg
                    pool = await asyncpg.create_pool(
                        host=host,
                        port=port or 5432,
                        database=database,
                        user=user,
                        password=password,
                        min_size=2,
                        max_size=10,
                        command_timeout=60
                    )
                    _connection_pools[pool_key] = pool
                    LOGGER.info(f"AsyncPG pool created for {resource_name}")
                except ImportError:
                    LOGGER.warning("asyncpg not available, skipping async PostgreSQL pool")
                except Exception as e:
                    LOGGER.error(f"Failed to create PostgreSQL pool for {resource_name}: {e}")

            elif provider_config.get('name') == 'MySQL':
                try:
                    import aiomysql
                    pool = await aiomysql.create_pool(
                        host=host,
                        port=port or 3306,
                        db=database,
                        user=user,
                        password=password,
                        minsize=2,
                        maxsize=10,
                        autocommit=True
                    )
                    _connection_pools[pool_key] = pool
                    LOGGER.info(f"AioMySQL pool created for {resource_name}")
                except ImportError:
                    LOGGER.warning("aiomysql not available, skipping async MySQL pool")
                except Exception as e:
                    LOGGER.error(f"Failed to create MySQL pool for {resource_name}: {e}")

    except Exception as e:
        LOGGER.error(f"Error initializing SQL pool for {resource_name}: {e}")


async def _init_mongo_pool(resource_name: str, provider_config: dict):
    """Initialize async MongoDB connection pool."""
    try:
        import motor.motor_asyncio

        connection_string = provider_config.get('data', '')
        if connection_string:
            client = motor.motor_asyncio.AsyncIOMotorClient(
                connection_string,
                maxPoolSize=10,
                minPoolSize=2,
                maxIdleTimeMS=30000,
                waitQueueTimeoutMS=5000
            )

            pool_key = f"mongo_{resource_name}"
            _connection_pools[pool_key] = client
            LOGGER.info(f"Motor MongoDB pool created for {resource_name}")

    except ImportError:
        LOGGER.warning("motor not available, skipping async MongoDB pool")
    except Exception as e:
        LOGGER.error(f"Error initializing MongoDB pool for {resource_name}: {e}")


async def _init_elasticsearch_pool(resource_name: str, provider_config: dict):
    """Initialize async Elasticsearch connection pool."""
    try:
        from elasticsearch import AsyncElasticsearch

        hosts = provider_config.get('data', 'localhost:9200')
        client = AsyncElasticsearch(
            hosts=[hosts] if isinstance(hosts, str) else hosts,
            max_retries=3,
            retry_on_timeout=True,
            timeout=30
        )

        pool_key = f"es_{resource_name}"
        _connection_pools[pool_key] = client
        LOGGER.info(f"Async Elasticsearch client created for {resource_name}")

    except ImportError:
        LOGGER.warning("elasticsearch[async] not available, skipping async Elasticsearch client")
    except Exception as e:
        LOGGER.error(f"Error initializing Elasticsearch client for {resource_name}: {e}")


async def cleanup_pools():
    """Clean up all connection pools on shutdown."""
    global _connection_pools

    for pool_name, pool in _connection_pools.items():
        try:
            if hasattr(pool, 'close'):
                if asyncio.iscoroutinefunction(pool.close):
                    await pool.close()
                else:
                    pool.close()
            LOGGER.info(f"Closed connection pool: {pool_name}")
        except Exception as e:
            LOGGER.error(f"Error closing pool {pool_name}: {e}")

    _connection_pools.clear()


# Create the ASGI application with async enhancements
def create_asgi_app() -> Starlette:
    """
    Create and configure the ASGI application with async optimizations.

    :returns: Configured Starlette ASGI application
    """
    # Start with the existing Starlette app
    app = STARLETTE_APP

    # Add async connection pool middleware
    app.add_middleware(AsyncConnectionPoolMiddleware, config=CONFIG)

    # Add shutdown event handler for cleanup
    @app.on_event("shutdown")
    async def shutdown_event():
        await cleanup_pools()
        LOGGER.info("Async pools cleaned up on shutdown")

    return app


# The ASGI application instance for gunicorn
APP = create_asgi_app()


def get_connection_pool(resource_name: str, pool_type: str = 'sql') -> Optional[Any]:
    """
    Get a connection pool for a specific resource.

    :param resource_name: Name of the resource
    :param pool_type: Type of pool ('sql', 'mongo', 'es')
    :returns: Connection pool instance or None
    """
    pool_key = f"{pool_type}_{resource_name}"
    return _connection_pools.get(pool_key)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        APP,
        host=CONFIG['server']['bind']['host'],
        port=CONFIG['server']['bind']['port'],
        log_level="info"
    )