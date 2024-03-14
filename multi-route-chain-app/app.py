#!/usr/bin/env python3

import os
import aws_cdk as cdk

from aws_cdk import Aspects
from cdk_nag import AwsSolutionsChecks
from cdk_nag import NagSuppressions

from multi_route_chain_app.base_infra_stack import BaseInfraStack
from multi_route_chain_app.sql_chain_stack import SqlChainStack
from multi_route_chain_app.rag_stack import RagStack
from multi_route_chain_app.action_lambda_stack import ActionLambdaStack
from multi_route_chain_app.frontend_stack import FrontendStack


app = cdk.App()

APP_PREFIX = "MultiRouteChain"
DATA_BUCKET_PREFIX = "data_bucket"
DEVICE_INFO_PATH = "iot_device_info"
DEVICE_DATA_PATH = "iot_device_metrics"
ATHENA_DB = "mrc_glue_db"
ATHENA_TABLE = "iot_device_metrics"
ATHENA_WORKGROUP = "mrc_athena_workgroup"
OSS_COLLECTION_NAME = "mrc-oss"
REGION = cdk.Aws.REGION

base_data_stack = BaseInfraStack(
    scope=app,
    construct_id=f"{APP_PREFIX}BaseInfraStack",
    bucket_name_prefix=DATA_BUCKET_PREFIX,
    iot_device_info=DEVICE_INFO_PATH,
    iot_device_data=DEVICE_DATA_PATH
)

sql_chain_stack = SqlChainStack(
    scope=app,
    construct_id=f"{APP_PREFIX}SqlChainStack",
    data_bucket=base_data_stack.data_bucket,
    data_path=DEVICE_DATA_PATH,
    athena_db=ATHENA_DB,
    athena_workgroup=ATHENA_WORKGROUP,
    app_execute_role=base_data_stack.app_execute_role)
sql_chain_stack.add_dependency(base_data_stack)

rag_stack = RagStack(
    scope=app,
    construct_id=f"{APP_PREFIX}RagStack",
    data_bucket_name=base_data_stack.data_bucket.bucket_name,
    data_path=DEVICE_INFO_PATH,
    oss_collection=OSS_COLLECTION_NAME,
    app_execute_role=base_data_stack.app_execute_role,
    vpc=base_data_stack.vpc)
rag_stack.add_dependency(base_data_stack)

action_lambda_stack = ActionLambdaStack(
    scope=app,
    construct_id=f"{APP_PREFIX}ActionLambdaStack")
action_lambda_stack.add_dependency(rag_stack)

app_env_vars = {
    "AWS_REGION": REGION,
    "STAGING_ATHENA_BUCKET": base_data_stack.data_bucket.bucket_name,
    "OPENSEARCH_ENDPOINT": rag_stack.opensearch_endpoint,
    "CUSTOM_CHAIN_LAMBDA": action_lambda_stack.lambda_arn,
    "ATHENA_SCHEMA": ATHENA_DB,
    "STREAMLIT_SERVER_PORT": "8501",
    "ATHENA_WORKGROUP": ATHENA_WORKGROUP,
    "MEMORY_TABLE": base_data_stack.memory_table.table_name
}

frontend_stack = FrontendStack(app, f"{APP_PREFIX}FrontendStack",
                               base_data_stack.app_execute_role,
                               base_data_stack.vpc,
                               app_env_vars)
frontend_stack.add_dependency(sql_chain_stack)
frontend_stack.add_dependency(rag_stack)
frontend_stack.add_dependency(action_lambda_stack)

Aspects.of(app).add(AwsSolutionsChecks())

# Base infra stack suppressions
NagSuppressions.add_stack_suppressions(base_data_stack, [
    {
        "id": "AwsSolutions-IAM4",
        "reason": "Suppress errors from aws_S3_deployment lib"
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "Suppress errors from aws_S3_deployment lib"
    },
    {
        "id": "AwsSolutions-L1",
        "reason": "Suppress errors from aws_S3_deployment lib"
    },
    {
        "id": "AwsSolutions-VPC7",
        "reason": "VPC Flow logs can be verbose and incur additional cost. This may be enabled by user if troubleshooting is needed"
    },
    {
        "id": "AwsSolutions-DDB3",
        "reason": "DynamoDB point in time backups should be enabled by customer if they wish to retain chat history."
    },
    
])

# Sql chain stack suppressions
NagSuppressions.add_stack_suppressions(sql_chain_stack, [
    {
        "id": "AwsSolutions-IAM4",
        "reason": "Glue role to populate Athena. Part of demo data population, not for the actual workload."
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "Glue role to populate Athena. Part of demo data population, not for the actual workload."
    },
    {
        "id": "AwsSolutions-GL1",
        "reason": "Glue Crawler is part of demo data population, not for the actual workload."
    },
    {
        "id": "AwsSolutions-ATH1",
        "reason": "Athena results are configured to be encrypted with SSE-S3"
    }
])

# Rag chain stack suppressions
NagSuppressions.add_stack_suppressions(rag_stack, [
    {
        "id": "AwsSolutions-IAM4",
        "reason": "CloudFormation custom resource lambda role. Part of bootstrap, not for the actual workload."
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "CloudFormation custom resource lambda role. Part of bootstrap, not for the actual workload."
    },
    {
        "id": "AwsSolutions-EC23",
        "reason": "Supress error for custom resource"
    },
    
])

# Action lambda chain stack suppressions
NagSuppressions.add_stack_suppressions(action_lambda_stack, [
    {
        "id": "AwsSolutions-IAM4",
        "reason": "Default lambda execute role provided."
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "Only validated SES identity can be used to send email."
    }
])

# Frontend stack suppressions
NagSuppressions.add_stack_suppressions(frontend_stack, [
    {
        "id": "AwsSolutions-CFR4",
        "reason": "When SSL Certificate is Default CloudFront Certificate (*.cloudfront.net), CloudFront automatically sets the security policy to TLSv1. User can enhance the solution with a custom certificate and enforce a higher TLS version"
    },
    {
        "id": "AwsSolutions-CFR5",
        "reason": "The origin is a Application Load Balancer with HTTP. A ACL rule is defined so that the Origin can only be accessed via CloudFront using HTTPS. User can enhance the solution with a custom certificate on the ALB and enforce HTTPS between CloudFront and the Origin."
    },
    {
        "id": "AwsSolutions-ELB2",
        "reason": "ELB access logs can be verbose and incur additional cost. This may be enabled by user if troubleshooting is needed."
    },
    {
        "id": "AwsSolutions-ECS4",
        "reason": "CloudWatch can be used to view logs from the ECS container. Container Insights may be enabled by user if further troubleshooting is needed."
    },
    {
        "id": "AwsSolutions-CFR1",
        "reason": "Geo restrictions may be enabled by user depending on their needs."
    },
    {
        "id": "AwsSolutions-ECS2",
        "reason": "Environment variables are used to point the application to dependent resources. No secrets are being passed with environment variables"
    },
    {
        "id": "AwsSolutions-CFR2",
        "reason": "WAF integration for this application is not needed for day 1. It can be enabled afterwards if required by the customer's security team."
    },
    {
        "id": "AwsSolutions-CFR3",
        "reason": "Access logging can be verbose and incur additional cost. This may be enabled by user if troubleshooting is needed."
    },
    {
        "id": "AwsSolutions-EC23",
        "reason": "Load balencer has ::/0 inbound access since it's internet facing"
    },
    {
        "id": "AwsSolutions-IAM5",
        "reason": "Default task excecute role permissions"
    }
])

app.synth()
