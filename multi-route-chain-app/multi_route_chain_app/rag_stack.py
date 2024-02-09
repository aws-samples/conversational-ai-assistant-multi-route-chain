"""Rag stack to provision OpenSearch vector search"""
import platform
import json
from constructs import Construct
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    Duration,
    aws_opensearchserverless as aws_opss,
    CustomResource,
    aws_lambda as _lambda,
    BundlingOptions,
    aws_iam as iam,
    aws_ec2 as ec2
)
from aws_cdk.custom_resources import Provider


class RagStack(Stack):
    """Rag stack to provision OpenSearch vector search"""

    def __init__(self, scope: Construct, construct_id: str,
                 data_bucket_name: str, data_path: str, oss_collection: str,
                 app_execute_role: iam.Role, vpc: ec2.Vpc) -> None:
        super().__init__(scope, construct_id)

        # in the given vpc, create opensearch client sg and cluster sg
        opensearch_client_sg = ec2.SecurityGroup(self, "OpensearchClientSg",
                                                 vpc=vpc,
                                                 allow_all_outbound=True,
                                                 description='security group for an opensearch client',
                                                 security_group_name='opensearch-client-sg'
                                                 )

        opensearch_cluster_sg = ec2.SecurityGroup(self, "OpensearchClusterSg",
                                                  vpc=vpc,
                                                  allow_all_outbound=True,
                                                  description='security group for an opensearch cluster',
                                                  security_group_name='opensearch-cluster-sg'
                                                  )
        opensearch_cluster_sg.add_ingress_rule(peer=ec2.Peer.ipv4(
            vpc.vpc_cidr_block), connection=ec2.Port.tcp(443), description='opensearch-cluster-sg')
        opensearch_cluster_sg.add_ingress_rule(peer=ec2.Peer.ipv4(
            vpc.vpc_cidr_block), connection=ec2.Port.tcp_range(9200, 9300), description='opensearch-cluster-sg')

        platform_mapping = {
            "x86_64": _lambda.Architecture.X86_64,
            "arm64": _lambda.Architecture.ARM_64
        }
        architecture = platform_mapping[platform.uname().machine]

        custom_res_lambda = _lambda.Function(
            self, "IndexOpenSearchLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset('multi_route_chain_app/rag_stack_custom_resources',
                                         bundling=BundlingOptions(
                                             image=_lambda.Runtime.PYTHON_3_11.bundling_image,
                                             command=['bash',
                                                      '-c',
                                                      'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output'])),
            handler='index.on_event',
            architecture=architecture,
            timeout=Duration.seconds(900),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[opensearch_client_sg]
        )

        custom_res_lambda.role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket"],
                resources=[
                    f"arn:aws:s3:::{data_bucket_name}",
                ]
            )
        )
        custom_res_lambda.role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[
                    f"arn:aws:s3:::{data_bucket_name}/*",
                ]
            )
        )
        custom_res_lambda.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v1"]
            )
        )

        vpc_endpoint = aws_opss.CfnVpcEndpoint(self, "OpssVpcEndpoint",
                                               name="opensearch-vpc-endpoint",  # Expected maxLength: 32
                                               vpc_id=vpc.vpc_id,
                                               security_group_ids=[
                                                   opensearch_cluster_sg.security_group_id],
                                               subnet_ids=vpc.select_subnets(
                                                   subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS).subnet_ids
                                               )
        vpc_endpoint.apply_removal_policy(cdk.RemovalPolicy.DESTROY)

        network_security_policy = json.dumps([{
            "Rules": [
                {
                    "Resource": [
                        f"collection/{oss_collection}"
                    ],
                    "ResourceType": "dashboard"
                },
                {
                    "Resource": [
                        f"collection/{oss_collection}"
                    ],
                    "ResourceType": "collection"
                }
            ],
            "AllowFromPublic": False,
            "SourceVPCEs": [
                vpc_endpoint.ref
            ]
        }], indent=2)

        cfn_network_security_policy = aws_opss.CfnSecurityPolicy(self, "NetworkSecurityPolicy",
                                                                 policy=network_security_policy,
                                                                 name=f"{oss_collection}-security-policy",
                                                                 type="network"
                                                                 )
        encryption_security_policy = json.dumps({
            "Rules": [
                {
                    "Resource": [
                        f"collection/{oss_collection}"
                    ],
                    "ResourceType": "collection"
                }
            ],
            "AWSOwnedKey": True
        }, indent=2)

        cfn_encryption_security_policy = aws_opss.CfnSecurityPolicy(self, "EncryptionSecurityPolicy",
                                                                    policy=encryption_security_policy,
                                                                    name=f"{oss_collection}-security-policy",
                                                                    type="encryption"
                                                                    )
        cfn_collection = aws_opss.CfnCollection(self, "OpssSearchCollection",
                                                name=oss_collection,
                                                description="Collection to be used for search using OpenSearch Serverless vector search",
                                                type="VECTORSEARCH"
                                                )
        cfn_collection.add_dependency(cfn_network_security_policy)
        cfn_collection.add_dependency(cfn_encryption_security_policy)

        data_access_policy = json.dumps([
            {
                "Rules": [
                    {
                        "Resource": [
                            f"collection/{oss_collection}"
                        ],
                        "Permission": [
                            "aoss:CreateCollectionItems",
                            "aoss:DeleteCollectionItems",
                            "aoss:UpdateCollectionItems",
                            "aoss:DescribeCollectionItems"
                        ],
                        "ResourceType": "collection"
                    },
                    {
                        "Resource": [
                            f"index/{oss_collection}/*"
                        ],
                        "Permission": [
                            "aoss:*",
                        ],
                        "ResourceType": "index"
                    }
                ],
                "Principal": [
                    f"{custom_res_lambda.role.role_arn}",
                    f"{app_execute_role.role_arn}"
                ],
                "Description": "data-access-rule"
            }
        ], indent=2)

        data_access_policy_name = f"{oss_collection}-access-policy"
        assert len(data_access_policy_name) <= 32

        aws_opss.CfnAccessPolicy(self, "OpssDataAccessPolicy",
                                 name=data_access_policy_name,
                                 description="Policy for data access",
                                 policy=data_access_policy,
                                 type="data"
                                 )

        custom_res_lambda.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "aoss:APIAccessAll",
                ],
                resources=["*"]
            )
        )

        custom_res_provider = Provider(self, "CustomResProvider",
                                       on_event_handler=custom_res_lambda,
                                       )

        custom_res = CustomResource(self, "IndexOpenSearch", service_token=custom_res_provider.service_token,
                                    properties={
                                        "oss_endpoint": cfn_collection.attr_collection_endpoint,
                                        "bucket_name": data_bucket_name,
                                        "data_path": data_path
                                    })
        custom_res.node.add_dependency(vpc_endpoint)
        custom_res.node.add_dependency(cfn_collection)

        self.opensearch_client_sg = opensearch_client_sg
        self.opensearch_endpoint = cfn_collection.attr_collection_endpoint
