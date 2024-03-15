"""BaseDataStack to provide a data bucket"""
import os
import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_dynamodb as dynamodb
)

dirname = os.path.dirname(__file__)


class BaseInfraStack(Stack):
    """BaseDataStack to provide a data bucket"""

    def __init__(self, scope: Construct, construct_id: str,
                 bucket_name_prefix: str, iot_device_info: str, iot_device_data: str) -> None:
        super().__init__(scope, construct_id)

        # create s3 bucket and upload sample data to the bucket
        data_bucket = s3.Bucket(self, bucket_name_prefix,
                                removal_policy=cdk.RemovalPolicy.DESTROY,
                                auto_delete_objects=True,
                                enforce_ssl=True,
                                server_access_logs_prefix="ServerAccessLogs"
                                )

        s3_deploy.BucketDeployment(self, "DeployDeviceMetrics",
                                   sources=[s3_deploy.Source.asset(
                                       os.path.join(dirname, f"../../../data/{iot_device_data}"))],
                                   destination_bucket=data_bucket,
                                   destination_key_prefix=iot_device_data
                                   )

        s3_deploy.BucketDeployment(self, "DeployDeviceInfo",
                                   sources=[s3_deploy.Source.asset(
                                       os.path.join(dirname, f"../../../data/{iot_device_info}"))],
                                   destination_bucket=data_bucket,
                                   destination_key_prefix=iot_device_info
                                   )
        self.data_bucket = data_bucket
        
        # DynamoDB table to hold app memory
        self.memory_table = dynamodb.Table(
            self, "SessionTable",
            partition_key=dynamodb.Attribute(
                name="SessionId",
                type=dynamodb.AttributeType.STRING
            ),
            # Additional properties like billing mode, encryption, etc., can be added here
            # For example, to use PAY_PER_REQUEST billing mode, uncomment the following line:
            # billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )

        # create app execute role
        app_execute_role = iam.Role(self, "AppExecuteRole",
                                    assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
                                    managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("AmazonAthenaFullAccess")]                
        )
        app_execute_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "aoss:APIAccessAll",
                    "lambda:InvokeFunction",
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=["*"]
            )  
        )
        
        app_execute_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:*",
                ],
                resources=[self.memory_table.table_arn]
            )  
        )
        
        data_bucket.grant_read_write(app_execute_role)
        self.app_execute_role = app_execute_role

        # create VPC to host the opensearch and ecs app
        vpc = ec2.Vpc(self, "MrcVpc",
                      ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
                      subnet_configuration=[
                          ec2.SubnetConfiguration(
                              name="public", subnet_type=ec2.SubnetType.PUBLIC),
                          ec2.SubnetConfiguration(
                              name="private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                          ec2.SubnetConfiguration(
                              name="isolated", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
                      ]
                      )
        self.vpc = vpc
