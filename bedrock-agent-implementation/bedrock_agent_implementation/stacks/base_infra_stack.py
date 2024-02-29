"""BaseDataStack to provide a data bucket"""
import os
import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_iam as iam,
    aws_glue as glue,
    aws_athena as athena,
    aws_ec2 as ec2,

)
from aws_cdk.custom_resources import (
    AwsCustomResource,
    AwsCustomResourcePolicy,
    PhysicalResourceId,
    AwsSdkCall
)


dirname = os.path.dirname(__file__)
APP_PREFIX = "IotOpsAgent"
DATA_BUCKET_PREFIX = "iot_ops_agent_asset_bucket"
DEVICE_INFO_PATH = "iot_device_info/"
DEVICE_DATA_PATH = "iot_device_metrics/"
ATHENA_DB = "iot_ops_glue_db"
ATHENA_TABLE = "iot_device_metrics"
ATHENA_WORKGROUP = "iot_ops_athena_workgroup"
REGION = cdk.Aws.REGION

class BaseInfraStack(Stack):
    """BaseDataStack to provide a data bucket"""

    def __init__(self, scope: Construct, construct_id: str,
                 bucket_name_prefix: str) -> None:
        super().__init__(scope, construct_id)

        # create s3 bucket and upload sample data to the bucket
        data_bucket = s3.Bucket(self, bucket_name_prefix,
                                removal_policy=cdk.RemovalPolicy.DESTROY,
                                auto_delete_objects=True,
                                enforce_ssl=True,
                                server_access_logs_prefix="ServerAccessLogs/"
                                )

        s3_deploy.BucketDeployment(self, "DeployDeviceMetrics",
                                   sources=[s3_deploy.Source.asset(
                                       os.path.join(dirname, f"../data/{DEVICE_DATA_PATH}"))],
                                   destination_bucket=data_bucket,
                                   destination_key_prefix=DEVICE_DATA_PATH
                                   )

        s3_deploy.BucketDeployment(self, "DeployDeviceInfo",
                                   sources=[s3_deploy.Source.asset(
                                       os.path.join(dirname, f"../data/{DEVICE_INFO_PATH}"))],
                                   destination_bucket=data_bucket,
                                   destination_key_prefix=DEVICE_INFO_PATH
                                   )
        # upload open API schemas
        s3_deploy.BucketDeployment(self, "OpenApiSchemas",
                                   sources=[s3_deploy.Source.asset(
                                       os.path.join(dirname, f"../action_groups/open_api_schema"))],
                                   destination_bucket=data_bucket,
                                   destination_key_prefix="open_api_schema"
                                   )

        self.data_bucket = data_bucket

        

        # Glue crawler role
        crawler_role = iam.Role(
            self,
            "IotOpsGlueRoleId",
            role_name="IotOpsGlueRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_managed_policy_arn(
                    self,
                    "GluePolicyID",
                    "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole",
                ),
            ],
        )
        data_bucket.grant_read_write(crawler_role)

        # set Glue crawler
        crawler = glue.CfnCrawler(
            self,
            "IotOpsGlueCrawlerId",
            name="IotOpsGlueCrawler",
            role=crawler_role.role_arn,
            database_name=ATHENA_DB,
            targets={
                "s3Targets": [
                    glue.CfnCrawler.S3TargetProperty(
                        path=f"s3://{data_bucket.bucket_name}/{DEVICE_DATA_PATH}"
                    )
                ]
            }
        )

        # custom resource to start the glue crawler
        res = AwsCustomResource(
            scope=self,
            id='AWSCustomResourceStartCrawler',
            policy=AwsCustomResourcePolicy.from_sdk_calls(
                resources=AwsCustomResourcePolicy.ANY_RESOURCE
            ),
            on_create=self.start_crawler(),
            on_delete=self.delete_glue_db(ATHENA_DB),
            resource_type='Custom::MyCustomResource'
        )

        res.node.add_dependency(crawler)

        # set up athena workgroup
        output_location=f"s3://{data_bucket.bucket_name}/athena_query_result/"
        athena.CfnWorkGroup(
            self,
            "IotOpsAthenaWorkgroupId",
            name=ATHENA_WORKGROUP,
            description="iot_ops_athena_workgroup",
            recursive_delete_option=True,
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=output_location,
                    encryption_configuration=athena.CfnWorkGroup.EncryptionConfigurationProperty(
                        encryption_option="SSE_S3"
                    )
                ),
            ),
        )

        self.athena_output_location = output_location
        self.athena_workgroup = ATHENA_WORKGROUP
        self.athena_db = ATHENA_DB

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


    def start_crawler(self):
        """start the glue crawler"""
        params = {
            "Name": "IotOpsGlueCrawler",
        }

        return AwsSdkCall(            
            service='@aws-sdk/client-glue',
            action='startCrawler',
            parameters=params,
            physical_resource_id=PhysicalResourceId.of(
                f'StartCrawler-IotOpsGlueCrawler')
        )

    def delete_glue_db(self, athena_db):
        """delete the glue db"""
        params = {
            "Name": athena_db,
        }

        return AwsSdkCall(            
            service='@aws-sdk/client-glue',
            action='deleteDatabase',
            parameters=params,
            physical_resource_id=PhysicalResourceId.of(
                f'DeleteDatabase-{athena_db}')
        )


