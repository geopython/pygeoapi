#!/bin/sh
if [ -z "${AWS_LAMBDA_RUNTIME_API}" ]; then
    exec /usr/bin/aws-lambda-rie /usr/bin/python3 -m awslambdaric $1
else
    exec /usr/bin/python3 -m awslambdaric $1
fi
