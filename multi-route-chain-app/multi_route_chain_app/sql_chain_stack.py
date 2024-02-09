"""SQL Chain stack to provision Athana catalog"""
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_glue as glue,
    aws_athena as athena,
    aws_s3 as s3,
)

from aws_cdk.custom_resources import (
    AwsCustomResource,
    AwsCustomResourcePolicy,
    PhysicalResourceId,
    AwsSdkCall
)


class SqlChainStack(Stack):
    """SQL Chain stack to provision Athana catalog"""

    def __init__(self, scope: Construct, construct_id: str,
                 data_bucket: s3.Bucket, data_path: str,
                 athena_db: str, athena_workgroup: str,
                 app_execute_role: iam.Role
                 ) -> None:
        super().__init__(scope, construct_id)

        self.crawler_name = "mrc_glue_crawler"
        self.crawler_role = "mrc_glue_role"

        # Glue crawler role
        crawler_role = iam.Role(
            self,
            "MrcGlueRoleId",
            role_name=self.crawler_role,
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
            "MrcGlueCrawlerId",
            name=self.crawler_name,
            role=crawler_role.role_arn,
            database_name=athena_db,
            targets={
                "s3Targets": [
                    glue.CfnCrawler.S3TargetProperty(
                        path=f"s3://{data_bucket.bucket_name}/{data_path}/"
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
            on_delete=self.delete_glue_db(athena_db),
            resource_type='Custom::MyCustomResource'
        )

        res.node.add_dependency(crawler)

        # set up athena workgroup
        athena.CfnWorkGroup(
            self,
            "MrcAthenaWorkgroupId",
            name=athena_workgroup,
            description="mrc_athena_workgroup",
            recursive_delete_option=True,
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{data_bucket.bucket_name}/athena_query_result/",
                    encryption_configuration=athena.CfnWorkGroup.EncryptionConfigurationProperty(
                        encryption_option="SSE_S3"
                    )
                ),
            ),
        )

    def start_crawler(self):
        """start the glue crawler"""
        params = {
            "Name": self.crawler_name,
        }

        return AwsSdkCall(
            action='startCrawler',
            service='Glue',
            parameters=params,
            physical_resource_id=PhysicalResourceId.of(
                f'StartCrawler-{self.crawler_name}')
        )

    def delete_glue_db(self, athena_db):
        """delete the glue db"""
        params = {
            "Name": athena_db,
        }

        return AwsSdkCall(
            action='deleteDatabase',
            service='Glue',
            parameters=params,
            physical_resource_id=PhysicalResourceId.of(
                f'DeleteDatabase-{athena_db}')
        )
