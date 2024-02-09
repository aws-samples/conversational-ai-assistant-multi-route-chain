# Multi-route chain infrastructure

## Repository struture

This repository helps to set up the multi-route chain app using [CDK](https://aws.amazon.com/cdk/). Specifically, it contains the following stacks:

- **MultiRouteChainBaseInfraStack**: it creates an S3 bucket and uploads all the data to be used by the Multi-route Chain APP to that bucket.
- **MultiRouteChainSqlChainStack**: it creates a Glue Crawler to crawl the data in the data bucket and sets up Athena data catelog.
- **MultiRouteChainRagStack**: it creates an OpenSearch serverless collection for vector search. And add the data into the index `docs`.
- **MultiRouteChainActionLambdaStack**: it creates an action lambda to send SES email.
- **MultiRouteChainFrontendStack**: it creates a Streamlit app running on ECS Fargate to interact with the LLM.

## Setup

### Pre-requisites
1. Enable models in Amazon Bedrock
2. SES setup (verify email)
3. [Get started with CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html)
4. [Install Docker](https://www.docker.com/get-started/). Because we are bundling Lambda functions when running CDK so we need to install Docker. Please see the blog post about [Building, bundling and deploying applications with the AWS CDK](https://aws.amazon.com/blogs/devops/building-apps-with-aws-cdk/)

### Run CDK
1. Change directory to `multi_route_chain_app`
    ```
    cdk synth -c sender=<the email verified in SES> -c recipient=<the email verified in SES> --all
    ```
2. Deploy the backend
    ```
    cdk deploy -c sender=<the email verified in SES> -c recipient=<the email verified in SES> --all --require-approval never
    ```

### Cleanup
Run the following commands to destroy all Stacks. 
```
cdk destroy -c sender=<the email verified in SES> -c recipient=<the email verified in SES> --all
```
Enter `y` upon the prompt to destroy each Stack.

### Other considerations

This section outlines additional security and cost related considerations for the solution

**Secure CDK deployments with IAM permission boundaries**

To initialize the CDK stack, we run `cdk bootstrap` which by default grants full `AdministratorAccess` to the CloudFormation deployment. For production deployments, we recommend following the [CDK security and safety development guide](https://github.com/aws/aws-cdk/wiki/Security-And-Safety-Dev-Guide) to properly configure least-privilege IAM permissions.

**Troubleshooting**

While interacting with the application you may encounter the following error in case an exception is thrown during request processing: `Error occurred when calling MultiRouteChain. Please review application logs for more information.`. In that case, please review the associated CloudWatch Logs log group for the exception name and detailed error message. To locate the correct log group, please navigate to the CloudWatch dashboard from the AWS Management Console and select **Log groups** from the left panel. Enter `Streamlit` in the log groups search box and select the log group title which begins with `MultiRouteChainFrontendStack`. Here you can select the Log stream associated with the error timeframe to troubleshoot further.

**CDK Nag Suppressions**

[cdk-nag](https://github.com/cdklabs/cdk-nag) is a tool used with the AWS Cloud Development Kit (CDK) to perform static analysis on your CDK application. It can help ensure the application complies with best practices and certain security baseline rules. Certain cdk-nag findings are suppressed for this solution which can be reviewed in the [app.py](app.py) file.

**CloudFront TLS Certificate Security Policy**

This soluton uses the Default CloudFront Certificate (*.cloudfront.net) which automatically sets the security policy to TLSv1. You may enforce a higher TLS version by associating your own TLS certificate to the CloudFront Distribution. Please reference [Supported protocols and ciphers between viewers and CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/secure-connections-supported-viewer-protocols-ciphers.html) and [Using HTTPS with CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-https.html#CNAMEsAndHTTPS)

**KMS Encryption for Athena query results**

The SQL Database chain in this solution uses Amazon Athena to run SQL queries on an S3 data source registered with the AWS Glue Data Catalog. You can optionally enable encryption at rest for Athena query results. Please follow the documentation link here for more information [Encrypting Athena query results stored in Amazon S3](https://docs.aws.amazon.com/athena/latest/ug/encrypting-query-results-stored-in-s3.html).

**Load balancer access logs and CloudWatch Container Insights**

This CDK project defines an Application Load Balancer as part of the [ApplicationLoadBalancedFargateService](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ecs_patterns/ApplicationLoadBalancedFargateService.html) construct. This contruct provides a Fargate service running on an ECS cluster fronted by an application load balancer. It is defined in the frontend Stack definition file [frontend_stack.py](/multi-route-chain-app/multi_route_chain_app/frontend_stack.py). The following features may be relevant for monitoring a troubleshooting the application.

- Elastic Load Balancing provides [access logs](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-access-logs.html) that capture detailed information about requests sent to your load balancer. Each log contains information such as the time the request was received, the client's IP address, latencies, request paths, and server responses. You can use these access logs to analyze traffic patterns and troubleshoot issues.

- You can use [CloudWatch Container Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContainerInsights.html) to collect, aggregate, and summarize metrics and logs from your containerized applications and microservices. CloudWatch automatically collects metrics for many resources, such as CPU, memory, disk, and network. Container Insights also provides diagnostic information, such as container restart failures, to help you isolate issues and resolve them quickly. To enable Container Insights
