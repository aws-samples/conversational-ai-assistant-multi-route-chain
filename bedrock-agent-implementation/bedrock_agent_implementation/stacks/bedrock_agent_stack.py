"""BedrockAgent stack to provide a Bedrock Agent"""
import platform
import json
from constructs import Construct
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    Duration,
    CustomResource,
    CfnParameter,
    aws_opensearchserverless as aws_opss,
    aws_lambda as _lambda,
    BundlingOptions,
    aws_iam as iam,
    aws_s3 as s3,
    custom_resources as cr
)

from aws_cdk.custom_resources import Provider

ACCOUNT_ID = cdk.Aws.ACCOUNT_ID
REGION = cdk.Aws.REGION

BEDROCK_AGENT_NAME = "IotOpsAgent"
FOUNDATION_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"
KNOWLEDGE_BASE_NAME = "IotDeviceSpecs"
EMBEDDING_MODEL = f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v1"
VECTOR_FIELD_NAME = "bedrock-agent-embeddings"
VECTOR_INDEX_NAME = "bedrock-agent-vector"
TEXT_FIELD = "AMAZON_BEDROCK_TEXT_CHUNK"
BEDROCK_META_DATA_FIELD = "AMAZON_BEDROCK_METADATA"
KNOWLEDGE_DATA_SOURCE = "IotDeviceSpecsS3DataSource"
KNOWLEDGE_BASE_DESC = "Knowledge base to search and retrieve IoT Device Specs"
OSS_COLLECTION = "bedrock-agent"

BEDROCK_AGENT_INSTRUCTION = f"""
As an IoT Ops agent, you handle managing and monitoring IoT devices: 
1. looking up device info in "{KNOWLEDGE_BASE_NAME}"
2. checking metrics from Athena "iot_ops_glue_db"."iot_device_metrics" table with columns:
    - name: oil_level type: double 
    - name: temperature type: double 
    - name: pressure type: double 
    - name: received_at type: string 
    - name: device_id type: bigint
    - name: device_name type: bigint
 When generating SQL queries, guidelines as follow:
    For "received_at" queries, use: SELECT * FROM iot_device_metrics WHERE parse_datetime(TRIM(BOTH '"' FROM received_at), 'yyyy-MM-dd HH:mm:ss') >= current_timestamp - interval. 
    For aggregate functions, include non-aggregated columns in GROUP BY, e.g., SELECT device_name, MAX(pressure) FROM iot_device_metrics GROUP BY device_name.
    group_id and group_name are integers, e.g. 1001
3. Perform actions like start, shutdown, reboot by device ID. 
4. Answering general questions.
"""
BEDROCK_AGENT_ALIAS="UAT"

class BedrockAgentStack(Stack):
    """class BedrockAgentStack(Stack): to provide a Bedrock Agent"""

    def __init__(self, scope: Construct, construct_id: str,
                 data_bucket: s3.Bucket, athena_db: str, 
                 athena_output_location: str) -> None:
        super().__init__(scope, construct_id)

        # create a custom resouce execution role to have admin access
        custom_res_role = iam.Role(
            self, "CustomResourceRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name="CustomResourceRole"
        )
        custom_res_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AdministratorAccess"
            )
        )

        # create a bedrock agent execution role
        bedrock_agent_role = iam.Role(
            self, "BedrockAgentRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            role_name=f"AmazonBedrockExecutionRoleForAgents_{BEDROCK_AGENT_NAME}"
        )
        data_bucket.grant_read_write(bedrock_agent_role)
        bedrock_agent_lambda_policy = iam.Policy(
            self, "BedrockAgentLambdaPolicy",
            policy_name="BedrockAgentLambdaPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"],
                    resources=["*"]
                )
            ]
        )
        bedrock_agent_s3_policy = iam.Policy(
            self, "BedrockAgentS3Policy",
            policy_name="BedrockAgentS3Policy",
            statements=[
                iam.PolicyStatement(
                    actions=["s3:GetObject"],
                    resources=["*"]
                )
            ]
        )
        bedrock_agent_model_policy = iam.Policy(
            self, "BedrockAgentModelPolicy",
            policy_name="BedrockAgentModelPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["bedrock:*"],
                    resources=["*"]
                )
            ]
        )
        bedrock_agent_role.attach_inline_policy(
            bedrock_agent_lambda_policy
        )
        bedrock_agent_role.attach_inline_policy(
            bedrock_agent_s3_policy
        )
        bedrock_agent_role.attach_inline_policy(
            bedrock_agent_model_policy
        )

        #create a bedrock knowledge base
        bedrock_kb_role = iam.Role(
            self, "BedrockKbRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            role_name=f"AmazonBedrockExecutionRoleForKnowledgeBase_{BEDROCK_AGENT_NAME}",
        )
        bedrock_kb_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AdministratorAccess"
            )        
        )

        # create aoss collection
        network_security_policy = json.dumps([{
            "Rules": [
                {
                    "Resource": [
                        f"collection/{OSS_COLLECTION}"
                    ],
                    "ResourceType": "dashboard"
                },
                {
                    "Resource": [
                        f"collection/{OSS_COLLECTION}"
                    ],
                    "ResourceType": "collection"
                }
            ],
            "AllowFromPublic": True,
        }], indent=2)

        cfn_network_security_policy = aws_opss.CfnSecurityPolicy(self, "NetworkSecurityPolicy",
                                                                 policy=network_security_policy,
                                                                 name=f"{OSS_COLLECTION}-security-policy",
                                                                 type="network"
                                                                 )
        encryption_security_policy = json.dumps({
            "Rules": [
                {
                    "Resource": [
                        f"collection/{OSS_COLLECTION}"
                    ],
                    "ResourceType": "collection"
                }
            ],
            "AWSOwnedKey": True
        }, indent=2)

        cfn_encryption_security_policy = aws_opss.CfnSecurityPolicy(self, "EncryptionSecurityPolicy",
                                                                    policy=encryption_security_policy,
                                                                    name=f"{OSS_COLLECTION}-security-policy",
                                                                    type="encryption"
                                                                    )
        cfn_collection = aws_opss.CfnCollection(self, "OpssSearchCollection",
                                                name=OSS_COLLECTION,
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
                            f"collection/{OSS_COLLECTION}"
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
                            f"index/{OSS_COLLECTION}/*"
                        ],
                        "Permission": [
                            "aoss:CreateIndex",
                            "aoss:DeleteIndex",
                            "aoss:UpdateIndex",
                            "aoss:DescribeIndex",
                            "aoss:ReadDocument",
                            "aoss:WriteDocument"
                        ],
                        "ResourceType": "index"
                    }
                ],
                "Principal": [
                    f"{custom_res_role.role_arn}",
                    f"{bedrock_agent_role.role_arn}",
                    f"{bedrock_kb_role.role_arn}",
                ],
                "Description": "data-access-rule"
            }
        ], indent=2)

        data_access_policy_name = f"{OSS_COLLECTION}-access-policy"
        assert len(data_access_policy_name) <= 32

        data_access_policy = aws_opss.CfnAccessPolicy(self, "OpssDataAccessPolicy",
                                 name=data_access_policy_name,
                                 description="Policy for data access",
                                 policy=data_access_policy,
                                 type="data"
                                 )
        data_access_policy.add_dependency(cfn_collection)
        
        # create aoss index
        platform_mapping = {
            "x86_64": _lambda.Architecture.X86_64,
            "arm64": _lambda.Architecture.ARM_64
        }
        architecture = platform_mapping[platform.uname().machine]
        index_res_lambda = _lambda.Function(
            self, "OpenSearchIndexLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset('bedrock_agent_implementation/custom_resource/aoss',
                                         bundling=BundlingOptions(
                                             image=_lambda.Runtime.PYTHON_3_11.bundling_image,
                                             command=['bash',
                                                      '-c',
                                                      'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output'])),
            handler='index.on_event',
            architecture=architecture,
            timeout=Duration.seconds(900),
            role=custom_res_role,
            environment={
                "VECTOR_FIELD_NAME": VECTOR_FIELD_NAME,
                "VECTOR_INDEX_NAME": VECTOR_INDEX_NAME,
                "TEXT_FIELD": TEXT_FIELD,
                "BEDROCK_META_DATA_FIELD": BEDROCK_META_DATA_FIELD,
            }
        )
        index_res_provider = Provider(self, "OpenSearchIndexResProvider",
                                       on_event_handler=index_res_lambda,
                                       )

        index_res = CustomResource(self, "IndexOpenSearch", service_token=index_res_provider.service_token,
                                    properties={
                                        "oss_endpoint": cfn_collection.attr_collection_endpoint,
                                    })
        index_res.node.add_dependency(data_access_policy)

        #create knowledge base with the opensearch index
        bedrock_kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=["aoss:APIAccessAll"],
                resources=[cfn_collection.attr_arn]
            )
        )
        bedrock_kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[EMBEDDING_MODEL]
            )
        )

        kb_res = cr.AwsCustomResource(
            scope=self,
            id='BedrockKowledgeBase',
            role=custom_res_role,
            on_create=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agent",
                action="CreateKnowledgeBase",
                parameters={
                    "knowledgeBaseConfiguration": {
                        "type": "VECTOR",
                        "vectorKnowledgeBaseConfiguration": {
                            "embeddingModelArn": EMBEDDING_MODEL
                        }
                    },
                    "name": KNOWLEDGE_BASE_NAME,
                    "roleArn": bedrock_kb_role.role_arn,
                    "storageConfiguration": {
                        "type": "OPENSEARCH_SERVERLESS",
                        "opensearchServerlessConfiguration": { 
                            "collectionArn": cfn_collection.attr_arn,
                            "fieldMapping": { 
                                "metadataField": BEDROCK_META_DATA_FIELD,
                                "textField": TEXT_FIELD,
                                "vectorField": VECTOR_FIELD_NAME
                                },
                            "vectorIndexName": VECTOR_INDEX_NAME
                        }
                    },
                },
                physical_resource_id=cr.PhysicalResourceId.from_response("knowledgeBase.knowledgeBaseId"),
                output_paths=["knowledgeBase.knowledgeBaseId"]
            ),
            on_delete=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agent",
                action="DeleteKnowledgeBase",
                parameters={
                    "knowledgeBaseId": cr.PhysicalResourceIdReference(),
                }
            )
        )
        kb_res.node.add_dependency(index_res)
        kb_res.node.add_dependency(bedrock_kb_role)
        knowledgebase_id = kb_res.get_response_field("knowledgeBase.knowledgeBaseId")
        
        # create data source
        data_source_res = cr.AwsCustomResource(
            scope=self,
            id='BedrockDataSource',
            role=custom_res_role,
            on_create=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agent",
                action="CreateDataSource",
                parameters={
                    "knowledgeBaseId": knowledgebase_id,
                    "name": KNOWLEDGE_DATA_SOURCE,
                    "dataDeletionPolicy": "RETAIN",
                    "dataSourceConfiguration": {
                        "type": "S3",
                        "s3Configuration": {
                            "bucketArn": data_bucket.bucket_arn,
                            "inclusionPrefixes": ["iot_device_info/"]
                        }
                    }
                },
                physical_resource_id=cr.PhysicalResourceId.from_response("dataSource.dataSourceId"),
                output_paths=["dataSource.dataSourceId"]
            )
        )  
        data_source_res.node.add_dependency(kb_res)
        datasource_id = data_source_res.get_response_field("dataSource.dataSourceId")
        # start datasource ingestion job
        ingestion_res = cr.AwsCustomResource(
            scope=self,
            id='BedrockIngestion',
            role=custom_res_role,
            on_create=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agent",
                action="StartIngestionJob",
                parameters={
                    "knowledgeBaseId": knowledgebase_id,
                    "dataSourceId": datasource_id,
                },
                physical_resource_id=cr.PhysicalResourceId.of("id"),
            )
        )
        ingestion_res.node.add_dependency(data_source_res)

        # create a bedrock agent
        agent_res = cr.AwsCustomResource(
            scope=self,
            id='BedrockAgent',
            role=custom_res_role,
            on_create=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agent",
                action="CreateAgent",
                parameters={
                    "agentName": BEDROCK_AGENT_NAME,
                    "agentResourceRoleArn": bedrock_agent_role.role_arn,
                    "foundationModel": FOUNDATION_MODEL,
                    "instruction": BEDROCK_AGENT_INSTRUCTION
                },
                physical_resource_id=cr.PhysicalResourceId.from_response("agent.agentId"),
                output_paths=["agent.agentId"]
            ),
            on_delete=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agent",
                action="DeleteAgent",
                parameters={
                    "agentId": cr.PhysicalResourceIdReference(),
                    "skipResourceInUseCheck": True
                }
            ),
        )
        agent_res.node.add_dependency(bedrock_agent_role)
        agent_res.node.add_dependency(bedrock_agent_lambda_policy)
        agent_res.node.add_dependency(bedrock_agent_s3_policy)
        agent_res.node.add_dependency(bedrock_agent_model_policy)
        agent_res.node.add_dependency(kb_res)

        agent_id = agent_res.get_response_field("agent.agentId")

        # update agent to associate with the knowledge base
        associate_agent_res = cr.AwsCustomResource(
            scope=self,
            id='BedrockAssociateKb',
            role=custom_res_role,
            on_create=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agent",
                action="AssociateAgentKnowledgeBase",
                parameters={
                    "agentId": agent_id,
                    "agentVersion": "DRAFT",
                    "knowledgeBaseId": knowledgebase_id,
                    "knowldeBaseState": "ENABLED",
                    "description": KNOWLEDGE_BASE_DESC
                },
                physical_resource_id=cr.PhysicalResourceId.of("id"),
            ) 
        )  
        associate_agent_res.node.add_dependency(data_source_res)
        associate_agent_res.node.add_dependency(agent_res)

        # action 1 is the device metrics lambda
        action_1_lambda = _lambda.Function(
            self, "DeviceMetricsLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset(
                'bedrock_agent_implementation/action_groups/check_device_metrics_query'),
            handler='lambda_function.lambda_handler',
            timeout=cdk.Duration.seconds(300),
            environment={
                'ATHENA_DATABASE': athena_db,
                'ATHENA_OUTPUT_LOCATION': athena_output_location
            },
        )
        action_1_lambda.add_permission(
            "AllowBedrockAgent",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_account=ACCOUNT_ID,
            source_arn=f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:agent/{agent_id}"
        )
        
        action_1_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonAthenaFullAccess")
        )
        data_bucket.grant_read_write(action_1_lambda.role)

        # action 2 is the device action lambda 
        sender = CfnParameter(self, "sender", type="String",
                              description="The sender's email for SES email notification")
        recipient = CfnParameter(self, "recipient", type="String",
                              description="The recipient's email for SES email notification")
        
        action_2_lambda = _lambda.Function(
            self, "DeviceActionLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset(
                'bedrock_agent_implementation/action_groups/action_on_device'),
            handler='lambda_function.lambda_handler',
            timeout=cdk.Duration.seconds(300),
            environment={
                'SENDER': sender.value_as_string,
                'RECIPIENT': recipient.value_as_string
            },
        )
        action_2_lambda.add_permission(
            "AllowBedrockAgent",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_account=ACCOUNT_ID,
            source_arn=f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:agent/{agent_id}"
        )

        action_2_lambda.role.add_to_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail"],
                resources=["*"]
            )
        )

        agent_action_group_res_1 = cr.AwsCustomResource(
            scope=self,
            id='BedrockAgentActionGroup1',
            role=custom_res_role,
            on_create=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agent",
                action="CreateAgentActionGroup",
                parameters={
                    "agentId": agent_id,
                    "agentVersion": "DRAFT",
                    "actionGroupExecutor": {
                        "lambda": action_1_lambda.function_arn,
                    },
                    "actionGroupName": "CheckDeviceMetricsActionGroup",
                    "actionGroupState": "ENABLED",
                    "apiSchema": {
                        "s3": {
                            "s3BucketName": data_bucket.bucket_name,
                            "s3ObjectKey": f"open_api_schema/check_device_metrics.json"
                        }
                    }
                },
                physical_resource_id=cr.PhysicalResourceId.from_response("agentActionGroup.actionGroupId"),
                output_paths=["agentActionGroup.actionGroupId"]
            )
        ) 

        agent_action_group_res_1.node.add_dependency(associate_agent_res)
        agent_action_group_res_1.node.add_dependency(action_1_lambda)

        agent_action_group_res_2 = cr.AwsCustomResource(
            scope=self,
            id='BedrockAgentActionGroup2',
            role=custom_res_role,
            on_create=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agent",
                action="CreateAgentActionGroup",
                parameters={
                    "agentId": agent_id,
                    "agentVersion": "DRAFT",
                    "actionGroupExecutor": {
                        "lambda": action_2_lambda.function_arn,
                    },
                    "actionGroupName": "ActionOnDeviceActionGroup",
                    "actionGroupState": "ENABLED",
                    "apiSchema": {
                        "s3": {
                            "s3BucketName": data_bucket.bucket_name,
                            "s3ObjectKey": f"open_api_schema/action_on_device.json"
                        }
                    }
                },
                physical_resource_id=cr.PhysicalResourceId.from_response("agentActionGroup.actionGroupId"),
                output_paths=["agentActionGroup.actionGroupId"]
            )
        ) 

        agent_action_group_res_2.node.add_dependency(associate_agent_res)
        agent_action_group_res_2.node.add_dependency(action_2_lambda)

        #prepare agent
        prepare_agent_res = cr.AwsCustomResource(
            scope=self,
            id='BedrockPrepareAgent',
            role=custom_res_role,
            on_create=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agent",
                action="PrepareAgent",
                parameters={
                    "agentId": agent_id
                },
                physical_resource_id=cr.PhysicalResourceId.of("id"),
                output_paths=["agentStatus"]
            )
        )

        prepare_agent_res.node.add_dependency(agent_action_group_res_1)
        prepare_agent_res.node.add_dependency(agent_action_group_res_2)

        #create agent alias
        agent_alias_res = cr.AwsCustomResource(
            scope=self,
            id='BedrockAgentAlias',
            role=custom_res_role,
            on_create=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agent",
                action="CreateAgentAlias",
                parameters={
                    "agentId": agent_id,
                    "agentAliasName": BEDROCK_AGENT_ALIAS
                },
                physical_resource_id=cr.PhysicalResourceId.of("id"),
                output_paths=["agentAlias.agentAliasId"]
            )
        )
        agent_alias_id = agent_alias_res.get_response_field("agentAlias.agentAliasId")
        agent_alias_res.node.add_dependency(prepare_agent_res)

        self.bedrock_agent_id = agent_id
        self.bedrock_agent_alias = agent_alias_id