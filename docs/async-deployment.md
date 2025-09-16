# Async Deployment with Gunicorn

This document explains how to deploy pygeoapi with async support using gunicorn and uvicorn workers for enhanced performance.

## Overview

pygeoapi now supports async operations through ASGI (Asynchronous Server Gateway Interface) with:
- Async database connection pooling
- Non-blocking I/O operations
- Better resource utilization
- Improved scalability

## Requirements

Install the async dependencies:

```bash
pip install -r requirements-async.txt
```

This includes:
- `asyncpg` for PostgreSQL async support
- `aiomysql` for MySQL async support
- `motor` for MongoDB async support
- `elasticsearch[async]` for Elasticsearch async support
- `gunicorn` and `uvicorn` for ASGI serving

## Basic Async Deployment

### Using the ASGI Application

Run pygeoapi with async support using the dedicated ASGI application:

```bash
# Basic uvicorn deployment
uvicorn pygeoapi.asgi_app:APP --host 0.0.0.0 --port 5000

# Gunicorn with uvicorn workers (recommended for production)
gunicorn pygeoapi.asgi_app:APP \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:5000 \
    --access-logfile - \
    --error-logfile -
```

### Advanced Gunicorn Configuration

For production environments:

```bash
gunicorn pygeoapi.asgi_app:APP \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:5000 \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --timeout 30 \
    --keep-alive 2 \
    --access-logfile /var/log/pygeoapi/access.log \
    --error-logfile /var/log/pygeoapi/error.log \
    --log-level info \
    --preload
```

## Configuration for Async Database Providers

### PostgreSQL with asyncpg

```yaml
resources:
  my_features:
    type: collection
    title: My Features
    providers:
      - type: feature
        name: AsyncSQLProvider  # Use the async provider
        data:
          host: localhost
          port: 5432
          database: mydb
          user: myuser
          password: mypass
        id_field: id
        table: features
        geom_field: geom
```

### MySQL with aiomysql

```yaml
resources:
  my_features:
    type: collection
    title: My Features
    providers:
      - type: feature
        name: AsyncSQLProvider
        data:
          host: localhost
          port: 3306
          database: mydb
          user: myuser
          password: mypass
        id_field: id
        table: features
        geom_field: geom
```

### MongoDB with motor

```yaml
resources:
  my_collection:
    type: collection
    title: My Collection
    providers:
      - type: feature
        name: AsyncMongoProvider
        data: mongodb://localhost:27017/mydb
        database: mydb
        collection: features
        id_field: _id
```

## Environment Variables

Set these environment variables for optimal async performance:

```bash
# Required for Starlette/ASGI
export PYGEOAPI_OPENAPI=/path/to/openapi.yml

# Optional: Async pool settings
export PYGEOAPI_ASYNC_POOL_MIN_SIZE=2
export PYGEOAPI_ASYNC_POOL_MAX_SIZE=10
export PYGEOAPI_ASYNC_POOL_TIMEOUT=30

# Gunicorn settings
export GUNICORN_WORKERS=4
export GUNICORN_WORKER_CLASS=uvicorn.workers.UvicornWorker
export GUNICORN_BIND=0.0.0.0:5000
```

## Docker Deployment

Example Dockerfile for async deployment:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt requirements-async.txt ./
RUN pip install -r requirements.txt -r requirements-async.txt

COPY . .

# Set environment variables
ENV PYGEOAPI_CONFIG=/app/config.yml
ENV PYGEOAPI_OPENAPI=/app/openapi.yml

# Expose port
EXPOSE 5000

# Run with gunicorn + uvicorn
CMD ["gunicorn", "pygeoapi.asgi_app:APP", \
     "-w", "4", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:5000"]
```

## Performance Tuning

### Worker Configuration

- **Workers**: Use 2-4 workers per CPU core
- **Worker Connections**: Set to 100-1000 depending on expected concurrent connections
- **Timeout**: Set appropriate timeouts for your use case (30-120 seconds)

### Database Connection Pools

The async application automatically configures connection pools with these defaults:
- **Min connections**: 2 per worker
- **Max connections**: 10 per worker
- **Connection timeout**: 30 seconds

### Memory Usage

Monitor memory usage as async applications can use more memory due to connection pooling:

```bash
# Monitor memory usage
ps aux | grep gunicorn
```

## Monitoring and Logging

### Application Logs

The async application provides detailed logging:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

### Health Checks

Add health check endpoints for monitoring:

```bash
# Check if the service is responding
curl http://localhost:5000/
```

### Metrics

Consider using tools like:
- Prometheus for metrics collection
- Grafana for visualization
- APM tools for performance monitoring

## Troubleshooting

### Common Issues

1. **Connection Pool Exhaustion**
   ```bash
   # Increase pool size in configuration
   export PYGEOAPI_ASYNC_POOL_MAX_SIZE=20
   ```

2. **Memory Issues**
   ```bash
   # Reduce workers or connection pool size
   gunicorn --workers 2 pygeoapi.asgi_app:APP
   ```

3. **Database Connection Issues**
   ```bash
   # Check database connectivity
   telnet db-host 5432
   ```

### Debug Mode

Run in debug mode for development:

```bash
uvicorn pygeoapi.asgi_app:APP --reload --log-level debug
```

## Migration from Sync to Async

### Step-by-Step Migration

1. **Install async dependencies**:
   ```bash
   pip install -r requirements-async.txt
   ```

2. **Update configuration** to use async providers where beneficial

3. **Test with uvicorn** first:
   ```bash
   uvicorn pygeoapi.asgi_app:APP --reload
   ```

4. **Deploy with gunicorn** for production:
   ```bash
   gunicorn pygeoapi.asgi_app:APP -k uvicorn.workers.UvicornWorker
   ```

### Backwards Compatibility

The async implementation maintains full backwards compatibility:
- Existing sync providers continue to work
- Configuration remains the same
- APIs are unchanged

## Performance Benefits

Expected improvements with async deployment:
- **Throughput**: 2-5x improvement for I/O-bound operations
- **Latency**: Reduced response times under load
- **Resource utilization**: Better CPU and memory efficiency
- **Scalability**: Handle more concurrent connections

Actual performance will vary based on your specific use case and infrastructure.