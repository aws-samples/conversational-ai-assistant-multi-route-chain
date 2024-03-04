#!/usr/bin/env python3

import aws_cdk as cdk

from bedrock_agent_implementation.stacks import base_infra_stack
from bedrock_agent_implementation.stacks import bedrock_agent_stack
from bedrock_agent_implementation.stacks import frontend_stack




app = cdk.App()
base_stack = base_infra_stack.BaseInfraStack(app, "BaseInfraStack", "IoTAgent")
agent_stack = bedrock_agent_stack.BedrockAgentStack(app, "BedrockAgentStack", data_bucket=base_stack.data_bucket, athena_db=base_stack.athena_db, athena_output_location=base_stack.athena_output_location)
frontend_stack.FrontendStack(app, "FrontendStack", bedrock_agent_id=agent_stack.bedrock_agent_id, bedrock_agent_alias=agent_stack.bedrock_agent_alias, vpc=base_stack.vpc)

app.synth()
