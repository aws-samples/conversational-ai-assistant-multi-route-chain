"""ActionLambdaStack to provision action lambda"""
import os
import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    Stack,
    CfnParameter,
    aws_iam as iam,
    aws_lambda as _lambda,
)

dirname = os.path.dirname(__file__)


class ActionLambdaStack(Stack):
    """ActionLambdaStack to provision action lambda"""

    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        sender = CfnParameter(self, "sender", type="String",
                              description="The sender's email for SES email notification")
        recipient = CfnParameter(self, "recipient", type="String",
                              description="The recipient's email for SES email notification")

        action_lambda = _lambda.Function(
            self, "SESActionLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset(
                'langchain_multi_route_implementation/ses_action_lambda'),
            handler='lambda_function.lambda_handler',
            environment={
                'SENDER': sender.value_as_string,
                'RECIPIENT': recipient.value_as_string
            },
        )

        action_lambda.role.add_to_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail"],
                resources=["*"]
            )
        )

        self.lambda_arn = action_lambda.function_arn
        cdk.CfnOutput(
            self, "SESActionLambdaArn",
            value=action_lambda.function_arn
        )
