# USING PyGeoAPI on AWS Lambda Serverless

The included serverless.yml and pygeoapi-serverless-config.yml can be used to deploy PyGeoAPI 
on AWS Lambda Serverless Environment.

This requires Amazon Credentials and the Serverless deployment tool.

AWS Credentials can be created following the instructions at https://serverless.com/framework/docs/providers/aws/guide/credentials/

To install the Serverless environment

```shell
npm install serverless
```

The following serverless plugins are also used

```
serverless plugin install -n serverless-python-requirements
serverless plugin install -n serverless-wsgi
```

To deploy to AWS Lambda:

```
serverless deploy
```

Once deployed, if you only need to update the code and not anything in the serverless configuration, you can update the function using:

```
serverless deploy --function app
```

When deployed, the output will show the URL the app has been deployed to.
