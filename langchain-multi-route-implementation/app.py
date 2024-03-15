#!/usr/bin/env python3

import aws_cdk as cdk

from langchain_multi_route_implementation.stacks.base_infra_stack import BaseInfraStack
from langchain_multi_route_implementation.stacks.sql_chain_stack import SqlChainStack
from langchain_multi_route_implementation.stacks.rag_stack import RagStack
from langchain_multi_route_implementation.stacks.action_lambda_stack import ActionLambdaStack
from langchain_multi_route_implementation.stacks.frontend_stack import FrontendStack


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

app.synth()
