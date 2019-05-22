#!/bin/bash

# pygeoapi entry script

echo "START /entrypoint.sh"

set +e

export PYGEOAPI_HOME=/pygeoapi
export PYGEOAPI_CONFIG="${PYGEOAPI_HOME}/local.config.yml"
export PYGEOAPI_OPENAPI="${PYGEOAPI_HOME}/local.openapi.yml"

# gunicorn env settings with defaults
SCRIPT_NAME=${SCRIPT_NAME:=/}
CONTAINER_NAME=${CONTAINER_NAME:=pygeoapi}
CONTAINER_HOST=${CONTAINER_HOST:=0.0.0.0}
CONTAINER_PORT=${CONTAINER_PORT:=80}
WSGI_WORKERS=${WSGI_WORKERS:=4}
WSGI_WORKER_TIMEOUT=${WSGI_WORKER_TIMEOUT:=6000}
WSGI_WORKER_CLASS=${WSGI_WORKER_CLASS:=gevent}

# What to invoke: default is to run gunicorn server
entry_cmd=${1:-run}

# Shorthand
function error() {
	echo "ERROR: $@"
	exit -1
}

# Workdir
cd ${PYGEOAPI_HOME}

echo "Trying to generate openapi.yml"
pygeoapi generate-openapi-document -c ${PYGEOAPI_CONFIG} > ${PYGEOAPI_OPENAPI}

[[ $? -ne 0 ]] && error "openapi.yml could not be generated ERROR"

echo "openapi.yml generated continue to pygeoapi"

case ${entry_cmd} in
	# Run Unit tests
	test)
	  for test_py in $(ls tests/test_*.py)
	  do
	    # Skip tests requireing backend server or libs installed
	    case ${test_py} in
	        tests/test_elasticsearch__provider.py)
	        ;&
	        tests/test_postgresql_provider.py)
	        	echo "Skipping: ${test_py}"
	        ;;
	        *)
	        	python3 -m pytest ${test_py}
	         ;;
	    esac
	  done
	  ;;

	# Run pygeoapi server
	run)
		# SCRIPT_NAME should not have value '/'
		[[ "${SCRIPT_NAME}" = '/' ]] && export SCRIPT_NAME="" && echo "make SCRIPT_NAME empty from /"

		echo "Start gunicorn name=${CONTAINER_NAME} on ${CONTAINER_HOST}:${CONTAINER_PORT} with ${WSGI_WORKERS} workers and SCRIPT_NAME=${SCRIPT_NAME}"
		gunicorn --workers ${WSGI_WORKERS} \
				--worker-class=${WSGI_WORKER_CLASS} \
				--timeout ${WSGI_WORKER_TIMEOUT} \
				--name=${CONTAINER_NAME} \
				--bind ${CONTAINER_HOST}:${CONTAINER_PORT} \
				pygeoapi.flask_app:APP
	  ;;
	*)
	  error "unknown command arg: must be run (default) or test"
	  ;;
esac

echo "END /entrypoint.sh"
