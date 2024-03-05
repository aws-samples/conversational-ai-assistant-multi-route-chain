from __future__ import annotations

import streamlit as st
import json
import boto3
import os

from langchain_core.output_parsers import StrOutputParser

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_community.embeddings import BedrockEmbeddings
from langchain_community.vectorstores import OpenSearchVectorSearch
from opensearchpy import RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import os
from langchain.llms.bedrock import Bedrock
from sqlalchemy import create_engine
from langchain_community.utilities.sql_database import SQLDatabase

import json
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import boto3  
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

# Check environment variables
required_envs = ["STAGING_ATHENA_BUCKET",
                 "OPENSEARCH_ENDPOINT", "CUSTOM_CHAIN_LAMBDA"]
for env in required_envs:
    if env not in os.environ:
        raise Exception("Required environment variable {} not set".format(env))

optional_envs = ["AWS_REGION", "ATHENA_SCHEMA"]
for env in optional_envs:
    if env not in os.environ:
        print("WARN: Environment variable {} not set, using default value".format(env))

# Setup variables
aws_region = os.environ.get('AWS_REGION', "us-west-2")

# setup Bedrock agent and LLM
bedrock = boto3.client("bedrock", aws_region)
llm = Bedrock(
    #    credentials_profile_name=profile_name,
    region_name=aws_region,
    model_id="anthropic.claude-v2:1",
    model_kwargs={'max_tokens_to_sample': 300,
                  'temperature': 0}
)

# Create the athena connection string
connathena = f"athena." + aws_region + ".amazonaws.com"
portathena = '443'
schemaathena = os.environ.get('ATHENA_SCHEMA', 'mrc_glue_db')
staging_athena_bucket = os.environ.get('STAGING_ATHENA_BUCKET')
s3stagingathena = ''.join(["S3://", staging_athena_bucket, "/"])

wkgrpathena = os.environ.get('ATHENA_WORKGROUP', 'mrc_athena_workgroup')
connection_string = f"awsathena+rest://{connathena}:{portathena}/{schemaathena}?s3_staging_dir={s3stagingathena}/&work_group={wkgrpathena}"


# Create the athena  SQLAlchemy engine
engine_athena = create_engine(connection_string, echo=False)
dbathena = SQLDatabase(engine_athena)
db = SQLDatabase(engine_athena)

# OpenSearch Endpoint
# Update the OpenSearch Endpoint
osendpoint = os.environ.get('OPENSEARCH_ENDPOINT')

# Lambda Function
lambda_function_name = os.environ.get(
    'CUSTOM_CHAIN_LAMBDA')  # Update the Lambda Function Name

import langchain_core
import langchain_community
st.title(f"Conversational AI - Plant Technician [Langchain version: {langchain_core.__version__}, Streamlit version: {st.__version__}, Langchain community version: {langchain_community.__version__}]")

##Define the Vector DB retriver 
def create_retriever():
    index_name = 'docs'
    endpoint = osendpoint 

    embeddings = BedrockEmbeddings(
        region_name = aws_region
    )

    vector_store = OpenSearchVectorSearch(
        index_name=index_name,
        embedding_function=embeddings,
        opensearch_url=endpoint,
        http_auth=get_aws4_auth(),
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )
    #print(vector_store.as_retriever())
    return vector_store.as_retriever()


def get_aws4_auth():
    region = aws_region
    service = "aoss"

    session = boto3.Session()
    credentials = session.get_credentials()


    if not credentials:
        raise ValueError("No AWS credentials found!")
    
    return AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        region,
        service,
        session_token=credentials.token,
    )
retriever = create_retriever()


#Setup Memory for chat history tracking 

msgs = StreamlitChatMessageHistory()
if len(msgs.messages) == 0:
    msgs.add_ai_message("How can I help you?")

#Defin the routing chain -  
router_prompt = ChatPromptTemplate.from_messages(
    [
        ("""Given the user question below, classify it as one of the candidate prompt. You may want to modify the input considering the chat history and the contex of the question. Sometimes the user may just assume that you have the context of the covnersation and may not provide a clear input. Hence, you are being provided with the chat history for more context. Respond  with only a Markdown code snippet containing a JSON object formatted EXACTLY as specified below. Do not provide an explaination to your calssification beside the Markdown, I just need to know your decision on which destination and next_inputs
<candidate prompt>
physics: Good for answering questions about physics
sql: sql: Good for quering sql from AWS Athena. User input may look like: get me max or min for device x?
lambdachain: Good to execute actions with Amazon Lambda like shutting down a device or turning off an engine User input can be like, shutdown device x, or terminate process y, etc
rag: Good to search knowldgebase and retriive information about devices and other related information. User question can be like: what do you know about device x?
default: if the input is not well suited for any of the candidate prompts above. this could be used to carry on the conversation and respond to queries like provide a summay of the conversation 
</candidate prompt>

<Markdown>
```json
{{
    "destination": string \ name of the prompt to use 
    "next_inputs": string \ a potentially modified version of the original input
}}
```
</Markdown>

<history> 
{history}
</history> 
<question>
{question}
</question>
""") 
    ]
)


chain = (
 router_prompt
    | llm
)

chain_with_history = RunnableWithMessageHistory(
    chain,
    lambda session_id: msgs,  # Always return the instance created earlier
    input_messages_key="question",
    history_messages_key="history",
)



#Defin all Destination chains including SQL, RAG, Lambda, SME, and default 

sql_prompt = ChatPromptTemplate.from_template(
"""
based on the table schema below, ONLY write a SQL query that would answer the user's question:
<schema>
    iot_device_metrics:
        fields:
        - name: device_name
        type: bigint
        - name: oil_level
        type: double
        - name: temperature
        type: double
        - name: pressure
        type: double
        - name: received_at
        type: string
        - name: device_id
        type: bigint
</schema>

- Use the folllowing SQL format when are being asked to generate a SQL that is using field name received_at i.e, "Query the data for the last 6 hours" 
            SELECT * 
            FROM iot_stream_analytics_out_iot201 
            WHERE parse_datetime(TRIM(BOTH '"' FROM received_at), 'yyyy-MM-dd HH:mm:ss') >= current_timestamp - interval '6' hour;
- For queries using aggregate functions, ensure non-aggregated columns are included in the GROUP BY clause to avoid the "EXPRESSION_NOT_AGGREGATE" error like this below. 
Incorrect: SELECT device_name, MAX(pressure) FROM table;
Correct: SELECT device_name, MAX(pressure) FROM table GROUP BY device_name;
Just generate the query and nothing else 

Example: 
Question: Give me max metrics for device 1007 
SELECT device_name, MAX(oil_level) AS max_oil_level, MAX(temperature) AS max_temperature, MAX(pressure) AS max_pressure
FROM iot_device_metrics 
WHERE device_id = 1007
GROUP BY 
device_name;     


Question: {next_inputs}

""" ) 

sql_result_prompt = ChatPromptTemplate.from_template("""You are an expert in heavy equipment IoT sensors data, use the table 'iot_device_metrics'
Based on the table schema below, question, sql query, and sql response, write a natural language response that provide a solid answer to the question. Do not explain what the SQL query is actually doing
<schema>
    iot_device_metrics:
        fields:
        - name: device_name
        type: bigint
        - name: oil_level
        type: double
        - name: temperature
        type: double
        - name: pressure
        type: double
        - name: received_at
        type: string
        - name: device_id
        type: bigint
</schema>

<Question>
{next_inputs}
</Question>

<SQLQuery> 
{query}
</SQLQuery> 

<SQLResponse> 
{response}
</SQLResponse> 

""")

def get_schema(_):
    return db.get_table_info()
# response1 = get_schema() 
# print(response1)

def run_query(query):
    return db.run(query)

sql_query_chain = (
    RunnablePassthrough.assign(schema=get_schema)
    | sql_prompt
    | llm.bind(stop=["\nSQLResult:"])
    | StrOutputParser()
)

sql_chain = (
    RunnablePassthrough.assign(query=sql_query_chain).assign(
        schema=get_schema,
        response=lambda x: db.run(x["query"]),
    )
    | sql_result_prompt
    | llm
)


lambda_client = boto3.client('lambda')  # Ensure AWS credentials are configured

def call_lambda_with_decision(decision):
    try:
        # Convert the decision dictionary to a JSON string, and then encode to bytes
        payload_bytes = json.dumps(decision).encode('utf-8')

        lambda_response = lambda_client.invoke(
            FunctionName=lambda_function_name,  # Replace with your actual Lambda function name
            InvocationType='RequestResponse',
            Payload=payload_bytes
        )
        lambda_output = json.loads(lambda_response['Payload'].read())
        return lambda_output.get("body", "")
    except Exception as e:
        print(f"Error during Lambda call: {str(e)}")
        return {"error": f"Error during Lambda call: {str(e)}"}

def lambda_decision_function(llm_response):
    # Parse the LLM response to extract the decision and deviceID
    try:
        response_data = json.loads(llm_response)
        decision = {"Action": response_data["Action"], "deviceID": response_data["deviceID"]}
        lambda_body = call_lambda_with_decision(decision)
        return lambda_body
    except json.JSONDecodeError:
        return {"error": "Failed to parse LLM response"}

lambda_execute_prompt = ChatPromptTemplate.from_template( """
You are a task executer 
Your job is execute the task by triggering a Lambda function when the user say somthing like shut down a device or turn on a device, turn on the fan, etc \

Use the following format:

<< FORMATTING >>
You MUST respond with a JSON object formatted EXACTLY as specified below.
I will repeat the REQUIRED FORMAT:

{{
    "Question": string \ Question here
    "Action": string \ Only the Action to take
    "deviceID": string \ Only the deviceID
}}

REMEMBER: use only one of the following actions. 

<<Actions>> 
- Shutdowndevice: deviceID
- turnondevice: deviceID
- restartdevice: deviceID 

Here is a question:
{next_inputs}
 
""" )

lambda_execute_chain = (
    lambda_execute_prompt
    | llm
    | RunnableLambda(lambda_decision_function)

)
lambda_prompt = ChatPromptTemplate.from_template( """
Provide one sentence to summarize the final decision for the user. Remember, just provide the summary. 
<Decision>
{lambda_output} 
</Decision>
""" )

lambda_chain = (
    {"lambda_output": lambda_execute_chain}
    | lambda_prompt
    | llm
)



physics_prompt = ChatPromptTemplate.from_messages(
    [
        ("""
You are a very smart physics professor. 
You are great at answering questions about physics in a concise and easy to understand manner. 
When you don't know the answer to a question you admit that you don't know.
Here is a question:
<question>{next_inputs}</question> 
<history>{history}</history>
""")
    ]
)

physics_chain_ = (

    physics_prompt 
    | llm
)

physics_chain = RunnableWithMessageHistory(
    physics_chain_,
    lambda session_id: msgs,  # Always return the instance created earlier
    input_messages_key="question",
    history_messages_key="history",
)

rag_prompt = ChatPromptTemplate.from_template(""" 

Answer the question based only on the following context:
<context>
{context}
</context>

<question>
{next_inputs}
</question>

""" ) 

rag_chain = (
    {"context": retriever, "next_inputs": RunnablePassthrough()}
    | rag_prompt
    | llm
    | StrOutputParser()
)


general_prompt = ChatPromptTemplate.from_messages(
    [
        ("""The following is a friendly conversation between a human and a AI. If the AI does not know the answer to a question, it truthfully says it does not know.
<history>{history}</history>
<question>{next_inputs}</question> 

Answer:""")
    ]
)

general_chain_ = (
     general_prompt 
    | llm
)

general_chain = RunnableWithMessageHistory(
    general_chain_,
    lambda session_id: msgs,  # Always return the instance created earlier
    input_messages_key="question",
    history_messages_key="history",
)

#Define the routing logic based on routing chain output --> to Dest chain 
import json

def route(info,config):
    topic = info["topic"].lower()
    print('Info:', info)
    #print('Topic:', topic)

    # Attempt to parse the JSON from the topic if it's in the expected format
    try:
        # Detecting and extracting the JSON string from the topic
        if "```json" in topic and "```" in topic:
            start = topic.find("```json") + len("```json")
            end = topic.find("```", start)
            json_str = topic[start:end].strip()  # Remove the markdown code block syntax and trim whitespaces
            parsed_json = json.loads(json_str)
            if 'next_inputs' in parsed_json:
                next_inputs = parsed_json['next_inputs']
                print('Next Inputs:', next_inputs)
                info['next_inputs'] = next_inputs
                info['next_inputs'] = next_inputs
            
            if 'destination' in parsed_json:
                destination = parsed_json['destination']
                print('Destination:', destination)
    except json.JSONDecodeError as e:
        print("Topic does not contain valid JSON:", e)

    # Use the 'destination' value in the routing logic
    if destination:
        print(msgs)
        if destination == "sql":
            return sql_chain.invoke(info)
        elif destination == "lambdachain":
            return lambda_chain.invoke(info)
        elif destination == "rag":
            return rag_chain.invoke(info["next_inputs"])
        elif destination == "physics":
            return physics_chain.invoke(info)
        else:
            return general_chain.invoke(info,config)
    else:
        # Fallback or default routing
        return general_chain.invoke(info)

# Defin the full chain which includs the routing and all dest chains 

full_chain = {"topic": chain_with_history, "question": lambda x: x["question"]} | RunnableLambda(
    route
)

full_chain_with_memory = RunnableWithMessageHistory(
    full_chain,
    lambda session_id: msgs,  # Always return the instance created earlier
    input_messages_key="question",
    history_messages_key="history",
)

# inputs = {"question": "Can you query max metrics for device 1009"}
# response = full_chain.invoke(inputs)
# print('Response:', response)
# memory.save_context(inputs, {"output": response})
# #memory.load_memory_variables({})

def main():
    for msg in msgs.messages:
        st.chat_message(msg.type).write(msg.content)

    if prompt := st.chat_input():
        st.chat_message("User").write(prompt)

        # As usual, new messages are added to StreamlitChatMessageHistory when the Chain is called.
        # Ensure 'session_id' is consistently passed in the configuration for all chain invocations.
        session_id = "any"  # You might want to generate or retrieve an actual session ID based on your application's logic
        config = {"configurable": {"session_id": session_id}}
        
        # Pass the same config to the full_chain invocation, ensuring that the session_id is included.
        response = full_chain.invoke({"question": prompt}, config)
        st.chat_message("ai").write(response)

if __name__ == '__main__':
    main()

