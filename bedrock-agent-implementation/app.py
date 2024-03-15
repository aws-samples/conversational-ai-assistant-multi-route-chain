#!/usr/bin/env python3

import aws_cdk as cdk

from bedrock_agent_implementation.stacks import base_infra_stack
from bedrock_agent_implementation.stacks import bedrock_agent_stack
from bedrock_agent_implementation.stacks import frontend_stack


APP_PREFIX = "BedrockAgentImpl"

app = cdk.App()
base_stack = base_infra_stack.BaseInfraStack(app, f"{APP_PREFIX}BaseInfraStack", "IoTAgent")
agent_stack = bedrock_agent_stack.BedrockAgentStack(app, f"{APP_PREFIX}GenAIStack", data_bucket=base_stack.data_bucket, athena_db=base_stack.athena_db, athena_output_location=base_stack.athena_output_location)
frontend_stack.FrontendStack(app, f"{APP_PREFIX}FrontendStack", bedrock_agent_id=agent_stack.bedrock_agent_id, bedrock_agent_alias=agent_stack.bedrock_agent_alias, vpc=base_stack.vpc)

app.synth()
