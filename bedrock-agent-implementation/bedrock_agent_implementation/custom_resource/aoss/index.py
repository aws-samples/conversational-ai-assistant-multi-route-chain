"""Custom resource lambda function to create OpenSearch index"""
import os
import time
import boto3
from opensearchpy import RequestsHttpConnection, OpenSearch
from requests_aws4auth import AWS4Auth

vector_field_name = os.environ.get("VECTOR_FIELD_NAME")
vector_index_name = os.environ.get("VECTOR_INDEX_NAME")
text_field = os.environ.get("TEXT_FIELD")
bedrock_metadata_field = os.environ.get("BEDROCK_META_DATA_FIELD")

def on_event(event, _):
    """Lambda handler"""
    print(event)
    request_type = event['RequestType']
    if request_type == 'Create':
        return on_create(event)
    if request_type == 'Update':
        return on_update(event)
    if request_type == 'Delete':
        return on_delete(event)
    raise Exception(f"Invalid request type: {request_type}")

def get_awsauth():
    """return awsauth with the current session credentials"""
    service = 'aoss'
    credentials = boto3.Session().get_credentials()
    region = os.environ['AWS_REGION']
    return AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        region,
        service,
        session_token=credentials.token,
    )

def get_opensearch_client(oss_endpoint, awsauth):
    """create opensearch client with the given credential and endpoint"""
    client = OpenSearch(
        hosts=[{'host': oss_endpoint.replace("https://", ""), 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=300
    )
    return client

def on_create(event):
    """create new resource"""
    props = event["ResourceProperties"]
    print(f"create new resource with props {props}" )
    oss_endpoint = props['oss_endpoint']
    time.sleep(60)
    awsauth = get_awsauth()
    client = get_opensearch_client(oss_endpoint, awsauth)
    if not client.indices.exists(vector_index_name):
        client.indices.create(
        vector_index_name,
        body={
            "settings": {
                "index": {
                    "number_of_shards": 2,
                    "knn.algo_param": {
                        "ef_search": 512
                    },
                    "knn": True,
                }
            },
            "mappings": {
                "properties": {
                    f"{bedrock_metadata_field}": {
                        "type": "text",
                        "index": False
                    },
                    f"{text_field}": {
                        "type": "text",
                        "index": True
                    },
                    f"{vector_field_name}": {
                        "type": "knn_vector",
                        "dimension": 1536,
                        "method": {
                            "engine": "faiss",
                            "name": "hnsw",
                            "parameters": {"ef_construction": 512, "m": 16},
                        }
                    }
                }
            },
        }
    )
    time.sleep(60)
    physical_id = "opensearch-index"
    return {'PhysicalResourceId': physical_id}

def on_update(event):
    """update the resource"""
    return on_create(event)


def on_delete(event):
    """delete the resource"""
    props = event["ResourceProperties"]
    print(f"delete resource with props {props}")
    physical_id = event["PhysicalResourceId"]
    print(f"delete resource {physical_id}")
    return {'PhysicalResourceId': physical_id}

