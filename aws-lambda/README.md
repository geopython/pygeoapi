# Using pygeoapi on AWS Lambda Serverless

## Overview

AWS Lambda Serverless is a service from Amazon that enables publishing
code which is executed as on demand functions.  The value is here is that
the server is only working when requests are made, resulting in more efficient
use of server resources as well as managing costs.

pygeoapi provides a couple of ways to publish to AWS Lambda depending on your
environment: zappa and node/serverless.

## zappa

[zappa](https://www.zappa.io) provides Python tooling to interact with AWS lambda.  Ensure the environment
variables `AWS_ACCESS_KEY` and `AWS_SECRET_ACCESS_KEY` are set and available.

```bash
# install zappa
pip install zappa

# set environment variables
export AWS_ACCESS_KEY_ID=foo
export AWS_SECRET_ACCESS_KEY=bar

# deploy pygeoapi to AWS Lambda
zappa deploy -s zappa_settings.json

# update
zappa update -s zappa_settings.json

# undeploy
zappa undeploy -s zappa_settings.json
```

## node/serverless

The included `serverless.yml` and `pygeoapi-serverless-config.yml` can be used to deploy pygeoapi
on AWS Lambda Serverless Environment. 

This requires Amazon Credentials and the Serverless deployment tool.

AWS Credentials can be created following the instructions at https://serverless.com/framework/docs/providers/aws/guide/credentials/

Move serverless configs to root directory:

```bash
mv serverless.yml ..
mv pygeoapi-server-config.yml ..
cd ..
```

To install the Serverless environment


```bash
npm install serverless
```

The following serverless plugins are also used

```bash
serverless plugin install -n serverless-python-requirements
serverless plugin install -n serverless-wsgi
```

To test the application as a lambda locally:

```bash
serverless wsgi server
```

To deploy to AWS Lambda:

```bash
serverless deploy
```

Once deployed, if you only need to update the code and not anything in the serverless configuration, you can update the function using:

```bash
serverless deploy --function app
```

When deployed, the output will show the URL the app has been deployed to.
