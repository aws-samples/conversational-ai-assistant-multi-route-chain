from __future__ import annotations
from langchain.chains.router import MultiPromptChain, MultiRouteChain
from langchain.chains import ConversationChain
from langchain.chains.llm import LLMChain
from langchain.prompts import PromptTemplate
import streamlit as st
import json
import boto3
import os
import sqlalchemy
from sqlalchemy import create_engine
from langchain.prompts.chat import SystemMessagePromptTemplate

from langchain.docstore.document import Document
from langchain.llms import SagemakerEndpoint
from langchain.prompts import PromptTemplate
from langchain.sql_database import SQLDatabase
from langchain.chains import LLMChain
from langchain_experimental.sql import SQLDatabaseChain
from langchain.llms.sagemaker_endpoint import LLMContentHandler
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts.prompt import PromptTemplate
from langchain.llms.bedrock import Bedrock

from langchain.chains.api.prompt import API_RESPONSE_PROMPT
from langchain.chains import APIChain
from langchain.prompts.prompt import PromptTemplate
from langchain.chat_models import ChatAnthropic
from langchain.chains.api import open_meteo_docs

from typing import Dict
from langchain.chains.router.llm_router import LLMRouterChain, RouterOutputParser
from langchain.chains.router.multi_prompt_prompt import MULTI_PROMPT_ROUTER_TEMPLATE
from typing import Dict, Any
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.chains import RetrievalQA
from langchain.memory.chat_message_histories import StreamlitChatMessageHistory

from typing import Any, Dict, List, Optional

import boto3
import json

from pydantic import Extra
from langchain.schema.language_model import BaseLanguageModel
from langchain.callbacks.manager import (
    AsyncCallbackManagerForChainRun,
    CallbackManagerForChainRun,
)
from langchain.chains.base import Chain
from langchain.prompts.base import BasePromptTemplate
from langchain.prompts.base import StringPromptTemplate

from langchain.embeddings import BedrockEmbeddings
from langchain.vectorstores import OpenSearchVectorSearch
from opensearchpy import RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Local module import for SQLDatabaseChain to work with Anthropic Claude. See sqldatabasechain.py for more information 
from sqldatabasechain import SQLDatabaseChain

import os

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
    model_id="anthropic.claude-v2",
    model_kwargs={'max_tokens_to_sample': 200,
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


# Define Chains Templates
lambda_template = """
                    Human: You are a task executer 
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
                    {input}
                    Assistant: 
"""

physics_template = """
                    Human: You are a very smart physics professor. 
                    You are great at answering questions about physics in a concise and easy to understand manner. 
                    When you don't know the answer to a question you admit that you don't know.

                    You can also consider this converstaion cotext to be smarter in repsonding back to the question 
                    {chat_history}

                    Here is a question:
                    {input}
                    Assistant: 
"""


sql_template = """Human: You are an expert in heavy equipment IoT sensors data, use the table 'iot_device_metrics'
Given an input question with SQLQuery: request, ONLY create a syntactically correct Amazon Athena query to run <SQL></SQL>. 
Given an input question input with Answer: request, provide a final <Answer></Answer>. 
Follow the <Instructions></Instructions> below.

Use the following <Format></Format> as a guide to see how the full conversation will look like. You need to respond to either: 
A Question with a SQLQuery request, in this case your response shold be a syntactically correct Amazon Athena query to run <SQL></SQL>. 
Or you need to responond to a Question followed by a SQLQuery, a SQLresult, and an Answer request, in this case you need to look into all available details and provide a final <Answer></Answer>
<Format> 
Question: "Question here"
SQLQuery: "SQL Query to run"
SQLResult: "Result of the SQLQuery"
Answer: "Final answer here for the of combination of Human inital input, the SQLQuery and the SQLResult"
</Format> 

Only use the following tables in the <schema></schema> below:                        
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

<Instructions> 
    - Given an input question with "SQLQuery:" request like in <Example 1></Example 1>, make sure you Just reposnd with the SQL Query Syntax alone. Write query in between <SQL></SQL>. Do not include SQLQuery: to your response 
    - Given an input question input with "Answer:" request like in <Example 2></Example 2>, make sure you: first, extract data from SQLResult. Then, interpret the data in context with the initial question. And last, Formulate a human-readable answer with no SQL. NO <SQL></SQL> Syntax in final Answer, Just the final answer in plain English like <Answer></Answer> 
    - Do not include double quote in SQLQuery
    - Just provide SQL Syntax in SQLQuery. 
    - Use the folllowing SQL format when are being asked to generate a SQL that is using field name received_at i.e, "Query the data for the last 6 hours" 
        <SQL>
            SELECT * 
            FROM iot_device_metrics 
            WHERE parse_datetime(TRIM(BOTH '"' FROM received_at), 'yyyy-MM-dd HH:mm:ss') >= current_timestamp - interval '6' hour;
        </SQL>
    - For queries using aggregate functions, ensure non-aggregated columns are included in the GROUP BY clause to avoid the "EXPRESSION_NOT_AGGREGATE" error like this below. 
    Incorrect: SELECT device_name, MAX(pressure) FROM table;
    Correct: SELECT device_name, MAX(pressure) FROM table GROUP BY device_name;
</Instructions> 

<Example 1>
    H:
    Question: Give me max metrics for device 1007 
    SQLQuery:
    A:
    <SQL>
        SELECT device_name, MAX(oil_level) AS max_oil_level, MAX(temperature) AS max_temperature, MAX(pressure) AS max_pressure
        FROM iot_device_metrics 
        WHERE device_id = 1007
        GROUP BY 
        device_name;     
    </SQL>
</Example 1>

<Example 2>
    H:
    Question: Give me max metrics for device 1007
    SQLQuery: 
    <SQL>
        SELECT device_name, MAX(oil_level) AS max_oil_level, MAX(temperature) AS max_temperature, MAX(pressure) AS max_pressure
        FROM iot_device_metrics 
        WHERE device_id = 1007 
        GROUP BY 
        device_name; 
    </SQL>
    SQLResult: [(1007, 197.5, 248.0, 99.0)] 
    Answer: 
    A:
    <Answer>
        The device with name 1007 had a maximum oil level of 197.5, a maximum temperature of 248.0, and a maximum pressure of 99.0.
    </Answer>
</Example 2>

<Question>
{input}
</Question>

Assistant:               
"""

rag_template = """
Human:
Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer. Consider the chat history below for additional context. 
<context>
{context}
</context>

Here is the chat history:
<chat history> 
{chat_history} 
</chat history> 

Here is a question:
<question>
{question}
</question>
Assistant:

"""


prompt_infos = [
    {
        "name": "physics",
        "description": "Good for answering questions about physics",
        "prompt_template": physics_template
    },
    {
        "name": "sql",
        "description": "Good for quering sql from AWS Athena. User input may look like: get me max or min for device x?",
        "prompt_template": sql_template
    },
    {
        "name": "lambdachain",
        "description": "Good to execute actions with Amazon Lambda like shutting down a device or turning off an engine User input can be like, shutdown device x, or terminate process y, etc",
        "prompt_template": lambda_template
    },
    {
        "name": "rag",
        "description": "Good to search knowldgebase and retriive information about devices and other related information. User question can be like: what do you know about device x?",
        "prompt_template": rag_template
    }
]

# CustomChain to Interact with a Lambda Function


class MyCustomChain(Chain):
    """
    An example of a custom chain.
    """

    prompt: BasePromptTemplate
    """Prompt object to use."""
    llm: BaseLanguageModel
    lambda_function_name: str
    output_key: str = "text"  #: :meta private:

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    @property
    def input_keys(self) -> List[str]:
        """Will be whatever keys the prompt expects."""
        return self.prompt.input_variables

    @property
    def output_keys(self) -> List[str]:
        """Will always return text key."""
        return [self.output_key]

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, str]:

        # boto3.setup_default_session(profile_name=profile_name)
        boto3.setup_default_session()
        lambda_client = boto3.client('lambda', aws_region)

        # Step 1: Use the input as a question for the LLM model
        prompt_value = self.prompt.format_prompt(**inputs)
        # print('prompt_value:', prompt_value)
        try:
            initial_response = self.llm.generate_prompt(
                [prompt_value],
                callbacks=run_manager.get_child() if run_manager else None
            )
            decision = initial_response.generations[0][0].text
            # print('decision: ', decision)
        except Exception as e:
            print(f"Error during initial LLM call: {e}")
            return {"error": "Error during initial LLM call"}

        # Step 2: Extract the device ID or whatever decision the LLM made
        # Assuming the decision has some format from which you can extract a device ID
        # device_id = extract_device_id_from_decision(decision)  # Implement this function as per your needs

        # Step 3: Invoke the Lambda function with the extracted device ID
        try:
            # Convert the decision dictionary to a JSON string, and then encode to bytes
            payload_bytes = json.dumps(decision).encode('utf-8')

            lambda_response = lambda_client.invoke(
                FunctionName=self.lambda_function_name,
                InvocationType='RequestResponse',
                Payload=payload_bytes
            )
            lambda_output = json.loads(lambda_response['Payload'].read())
        except Exception as e:
            print(f"Error during Lambda call: {str(e)}")
            return {"error": f"Error during Lambda call: {str(e)}"}

        lambda_body = lambda_output.get("body", "")

        try:
            evaluation_input = f"“ {inputs} \nAssistant: {lambda_body} \nHuman: Provide one sentence to summarize the final decision for the user. Remember, just provide the summary"
            evaluation_input = {
                'input': evaluation_input

            }
            prompt_value = self.prompt.format_prompt(**evaluation_input)
            # print('prompt_value: ', prompt_value)
            # print('evaluation_input:', evaluation_input)
            final_response = self.llm.generate_prompt(
                [prompt_value],
                callbacks=run_manager.get_child() if run_manager else None
            )
            final_decision = final_response.generations[0][0].text
        except Exception as e:
            print(f"Error during final LLM call: {e}")
            return {"error": "Error during final LLM call"}

        # Step 5: Return the final answer
        return {
            self.output_key: final_decision
        }

    @property
    def _chain_type(self) -> str:
        return "my_custom_chain"


# Defin the Vecotr DB retriver
def create_retriever():
    index_name = 'docs'
    endpoint = osendpoint

    embeddings = BedrockEmbeddings(
        # credentials_profile_name=profile_name, region_name="us-east-1"
        region_name=aws_region
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
    # print(vector_store.as_retriever())
    return vector_store.as_retriever()


def get_aws4_auth():
    region = aws_region
    service = "aoss"

    # session = boto3.Session(profile_name=profile_name)
    session = boto3.Session()
    credentials = session.get_credentials()

    if not credentials:
        raise ValueError("No AWS credentials found!")

    return AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        region,
        service,
        session_token=credentials.token
    )


retriever = create_retriever()

# Define first message in ChatHistory
msgs = StreamlitChatMessageHistory(key="langchain_messages")
if len(msgs.messages) == 0:
    msgs.add_ai_message("How can I help you?")


# Memory Function
def get_memory(output_key=None):
    return ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key=output_key,
        chat_memory=msgs
    )


# Function to create the detination chains
def _create_destination_chains(prompt_infos, llm, db, shared_memory):
    destination_chains = {}

    for p_info in prompt_infos:
        name = p_info["name"]
        prompt_template = p_info["prompt_template"]

        # If it's the SQL chain, use the promptsql
        if name == "sql" or name == "lambdachain":
            prompt = PromptTemplate(
                template=prompt_template, input_variables=["input"])
        elif name == "rag":
            prompt = PromptTemplate(template=prompt_template, input_variables=[
                                    "question", "context", "chat_history"])
        else:
            prompt = PromptTemplate(template=prompt_template, input_variables=[
                                    "input", "chat_history"])

        output_key = "text"  # Set a consistent output key here

        # Check which chain to create based on 'chain_type'
        if p_info["name"] == "physics":
            chain = LLMChain(llm=llm, prompt=prompt,
                             memory=shared_memory, output_key=output_key)
        elif p_info["name"] == "sql":
            # memory=shared_memory, output_key=output_key)
            chain = SQLDatabaseChain.from_llm(
                llm, db, verbose=True, prompt=prompt, return_intermediate_steps=True, output_key=output_key)
            # hain = LLMChain(llm=llm, prompt=prompt, memory=shared_memory, output_key=output_key)
        elif p_info["name"] == "lambdachain":

            # Change the Lambda function name to match yours if different
            chain = MyCustomChain(
                llm=llm, prompt=prompt, lambda_function_name=lambda_function_name, output_key=output_key)
        elif p_info["name"] == "rag":
            # print('PROMPT:', prompt)
            chain = ConversationalRetrievalChain.from_llm(
                llm, retriever=retriever, memory=shared_memory, output_key=output_key, combine_docs_chain_kwargs={"prompt": prompt})

        else:
            raise ValueError(f"Unknown chain type: {p_info['name']}")

        destination_chains[name] = chain

    return destination_chains


# Customer Parser to deal with the different LangChain Inputs
class CustomRouterOutputParser(RouterOutputParser):

    def parse(self, text: str) -> Dict[str, Any]:
        result = super().parse(text)

        # Modify the key based on the destination
        destination = result.get("destination")
        if result.get("destination") == "sql":
            # pass
            sql_input = result['next_inputs'].get('input')
            if sql_input:
                result['next_inputs'] = {'query': sql_input}
            if 'input' in result['next_inputs']:
                del result['next_inputs']['input']

        elif result.get("destination") == "physics":
            # If any modifications needed
            pass

        elif result.get("destination") == "rag":
            rag_input = result['next_inputs'].get('input')
            # print('rag_input:', rag_input)
            if rag_input:
                result['next_inputs'] = {'question': rag_input}
            if 'input' in result['next_inputs']:
                del result['next_inputs']['input']

        result["chain_destination"] = destination
        print(result)
        return result


# The Router Chain
def _create_router_chain(prompt_infos, shared_memory):
    destinations = [f"{p['name']}: {p['description']}" for p in prompt_infos]
    destinations_str = "\n".join(destinations)

    router_template = """ \n\nHuman:
                        Given a raw text input and the chat history to a language model select the model prompt best suited for the input. You will be given the names of the available prompts and a description of what the prompt is best suited for. 
                        You may want to modify the input considering the chat history and the contex of the question. Sometimes the user may just assume that you have the context of the covnersation and may not provide a clear input. Hence, you are being provided with the chat history for more context
                        
                        << FORMATTING >>
                        You MUST respond with a Markdown code snippet containing a JSON object formatted EXACTLY as specified below.
                        I will repeat the REQUIRED FORMAT:
                        ```json
                        {{
                            "destination": string \ name of the prompt to use or "DEFAULT"
                            "next_inputs": string \ a potentially modified version of the original input
                        }}
                        ```

                        REMEMBER: "destination" MUST be one of the candidate prompt names specified below OR it can be "DEFAULT" if the input is not well suited for any of the candidate prompts.
                        REMEMBER: "next_inputs" can just be the original input if you don't think any modifications are needed.
                        REMEMBER: if you find the answer in chat history, then route the question to default and provide original input if you don't think any modifications are needed.

                        << CANDIDATE PROMPTS >>
                        physics: Good for answering questions about physics
                        sql: sql: Good for quering sql from AWS Athena. User input may look like: get me max or min for device x?
                        lambdachain: Good to execute actions with Amazon Lambda like shutting down a device or turning off an engine User input can be like, shutdown device x, or terminate process y, etc
                        rag: Good to search knowldgebase and retriive information about devices and other related information. User question can be like: what do you know about device x?

                        <<chat history>> 
                        {chat_history}
                        << INPUT >>
                        {input}

                        << OUTPUT (must include ```json at the start of the response) >>
                        << OUTPUT (must end with ```) >> 
                        \n\nAssistant:
                    """

    router_prompt = PromptTemplate(
        template=router_template,
        input_variables=["input", "chat_history"],
        output_parser=CustomRouterOutputParser(),
    )
    return LLMRouterChain.from_llm(llm, router_prompt)


def get_prompt():
    template = """\n\nHuman:The following is a friendly conversation between a human and a Augmented Generation Virtual Assistant. If the AI does not know the answer to a question, it truthfully says it does not know.

    Current conversation:
    {chat_history}

    Question: {input}
    \n\nAssistant:"""
    input_variables = ["input", "chat_history"]
    prompt_template_args = {
        "chat_history": "{chat_history}",
        "input_variables": input_variables,
        "template": template,
    }
    prompt_template = PromptTemplate(**prompt_template_args)

    return prompt_template


shared_memory = get_memory(output_key="text")

destination_chains = _create_destination_chains(
    prompt_infos, llm, db, shared_memory)
router_chain = _create_router_chain(prompt_infos, shared_memory)


default_chain = LLMChain(llm=llm, prompt=get_prompt(), memory=shared_memory)

chain = MultiRouteChain(
    memory=shared_memory,
    router_chain=router_chain,
    destination_chains=destination_chains,
    default_chain=default_chain,
    verbose=True,
)


def main():
    st.title("Conversational AI - Plant Technician")

    # Initialize the conversation state
    if 'conversation' not in st.session_state:
        st.session_state.conversation = []

    # Taking user input
    user_prompt = st.text_input("Message:")

    if user_prompt:
        try:
            # Add the user's prompt to the conversation state
            st.session_state.conversation.append({'user': user_prompt})
            # print('shared_memory: ', shared_memory )
            # Execute the main logic of your application
            answer = chain(user_prompt)

            # Format and add the answer to the conversation state
            if 'query' in answer and 'result' in answer:
                formatted_answer = f"{answer['query']} - {answer['result']}"
            elif 'answer' in answer:
                formatted_answer = answer['answer']
            elif 'result' in answer:
                formatted_answer = answer['result']
            elif 'text' in answer:
                lambda_response_text = answer.get('lambda_response', "")
                formatted_answer = f"{answer['text']} {lambda_response_text}".strip(
                )
            else:
                formatted_answer = "Unknown response format"

            st.session_state.conversation.append(
                {'assistant': formatted_answer})

        except Exception as e:
            # Display an error message if an exception occurs
            st.error(f"Error occurred when calling MultiRouteChain. Please review application logs for more information.")
            print(f"ERROR: Exception when calling MultiRouteChain: {e}")
            formatted_answer = f"Error occurred: {e}"
            st.session_state.conversation.append(
                {'assistant': formatted_answer})

# Display the conversation
    for interaction in st.session_state.conversation:
        with st.container():
            if 'user' in interaction:
                # Apply a custom color to the "User" alias using inline CSS
                st.markdown(f'<span style="color: #4A90E2; font-weight: bold;">User:</span> {interaction["user"]}', unsafe_allow_html=True)
            else:
                # Apply a different custom color to the "Assistant" alias using inline CSS
                st.markdown(f'<span style="color: #50E3C2; font-weight: bold;">Assistant:</span> {interaction["assistant"]}', unsafe_allow_html=True)

if __name__ == '__main__':
    main()
