"""Custom resource lambda function to create OpenSearch index"""
import os
import time
import boto3
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import BedrockEmbeddings
from langchain.vectorstores import OpenSearchVectorSearch
from langchain.document_loaders import DirectoryLoader, TextLoader
from opensearchpy import RequestsHttpConnection, OpenSearch
from requests_aws4auth import AWS4Auth

bedrockruntime = boto3.client(service_name='bedrock-runtime')
embeddings = BedrockEmbeddings(client=bedrockruntime)

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
    bucket_name = props['bucket_name']
    oss_endpoint = props['oss_endpoint']
    data_path = props['data_path']
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    if not os.path.exists('/tmp/data'):
        os.makedirs('/tmp/data')
    for obj in bucket.objects.filter(Prefix=data_path):
        filename = obj.key.split('/')[-1]
        local_file_name = f'/tmp/data/{filename}'
        print(local_file_name)
        bucket.download_file(obj.key, local_file_name)
    loader = DirectoryLoader('/tmp/data', loader_cls=TextLoader)
    docs = loader.load()
    print(len(docs))
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, length_function=len
    )
    docs = text_splitter.split_documents(docs)
    print(len(docs))
    awsauth = get_awsauth()
    client = get_opensearch_client(oss_endpoint, awsauth)
    if not client.indices.exists('docs'):
        client.indices.create(
        'docs',
        body={
            "settings": {
                "index.knn": True,
            },
            "mappings": {
                "properties": {
                    "vector_field": {
                        "type": "knn_vector",
                        "dimension": 1536,
                    },
                }
            }
        }
    )
        time.sleep(60)
    OpenSearchVectorSearch.from_documents(
        docs,
        embeddings,
        opensearch_url=oss_endpoint,
        http_auth=awsauth,
        timeout=300,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        index_name="docs",
    )

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
