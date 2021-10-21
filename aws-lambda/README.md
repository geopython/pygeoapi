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
mv pygeoapi-config.yml ..
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
serverless wsgi serve
```

To deploy to AWS Lambda:

```bash
serverless deploy
```

Once deployed, if you only need to update the code and not anything in the serverless configuration, you can update the function using:

```bash
serverless deploy function -f app
```

When deployed, the output will show the URL the app has been deployed to.

## node/serverless lambda container

In the case where your pygeoapi instance is too large to deploy as a lambda function (250MB) you can build and deploy
a docker image of pygeoapi with the lamda runtime interface installed. 

Move serverless configs to root directory:

```bash
mv container/serverless.yml ../..
mv container/DockerFile ../..
```

*note the files below come from the serverless-wsgi node plugin, and ideally this should be part of a build process
```bash
cd container/
npm install serverless
serverless plugin install -n serverless-wsgi
mv node_modules/serverless-wsgi/serverless-wsgi.py ../..
mv node_modules/serverless-wsgi/wsgi_handler.py ../..
mv container/wsgi.py ../..
mv container/.serverless-wsgi ../..
rm -rf container/node_modules
cd ../..
```

# to build docker container
```bash
docker build -t pygeo-lambda-container .
```

Once built, you need to deploy to ECR. This can also be accomplished with a change to the serverless configuration.
Depending on environment permissions, you may need to create a ECR repo with appropriate policies first.

```bash
AWS_PROFILE=<profile name> aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <ECR repo url>
docker tag pygeo-lambda-container:latest <ECR repo url>:latest
docker push <ECR repo url>:latest
```


Deploy stack using serverless. 

```
AWS_PROFILE=<profile name> sls deploy -s <stage name>
```
