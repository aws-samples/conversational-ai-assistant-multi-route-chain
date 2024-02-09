# Multi-Route Chain Application - Building an Advanced Conversational AI Assistant

## Content
- [Overview](#overview)
- [Solution Architecture](#solution-architecture)
- [Technical Deep Dive](#technical-deep-dive)
- [How to Use](#how-to-use)


## Overview

This repository provides a step-by-step guide on creating a Conversational AI assistant that intelligently routes user inputs to the most relevant chatbot function, enhancing user interaction through precise and context-aware responses. It leverages AWS services such as [Amazon Bedrock](https://aws.amazon.com/bedrock) a fully managed service that offers a choice of high-performing foundation models (FMs) from leading AI companies like AI21 Labs, Anthropic, Cohere, Meta, Stability AI, and Amazon via a single API. For this project, we specifically employ the Anthropic Claude V2 model alongside [Langchain](https://python.langchain.com/docs/integrations/llms/bedrock) to deliver various capabilities.

- **Querying Databases**: Demonstrates how to query an Athena database using Langchain's [SQLDatabaseChain](https://python.langchain.com/docs/use_cases/qa_structured/sql), enabling the AI to fetch and present data directly from structured databases in response to user queries.
- **Semantic Searches**: Shows how to perform advanced semantic searches within an OpenSearch Vector index by integrating Langchain's [ConversationalRetrievalChain](https://api.python.langchain.com/en/latest/chains/langchain.chains.conversational_retrieval.base.ConversationalRetrievalChain.html) and [OpenSearch](https://python.langchain.com/docs/integrations/vectorstores/opensearch), enhancing the AI's ability to understand and retrieve relevant information based on the context of the conversation.
- **Triggering Lambda Functions**: Illustrates how to execute custom Lambda functions for specific tasks through Langchain's [Custom Chain](https://python.langchain.com/docs/modules/chains/how_to/custom_chain), allowing for a wide range of actions, from data manipulation to initiating workflows, based on user requests.
- **Specialized Chatbot Interactions**: Explains how to use Langchain's [LLMChain](https://api.python.langchain.com/en/latest/chains/langchain.chains.llm.LLMChain.html#langchain.chains.llm.LLMChain) for engaging in specialized conversations and performing tasks by leveraging large language models, ensuring that the AI can handle a variety of user intents with high precision.
- **Natural Conversational Engagement**: Focuses on using the same [LLMChain](https://api.python.langchain.com/en/latest/chains/langchain.chains.llm.LLMChain.html#langchain.chains.llm.LLMChain) to maintain a natural and fluid conversation flow, making interactions feel more human-like and intuitive.

A key aspect covered is the preservation of conversation context and chat history, which is crucial for the AI to understand the user's ongoing intent and provide responses that are coherent and contextually enriched. For details on how context is maintained and utilized to enhance conversations, the repository includes information on [Langchain memory](https://python.langchain.com/docs/modules/memory/) techniques.

This repository serves as a comprehensive guide for developers looking to build sophisticated Conversational AI systems that can intelligently navigate and respond to a wide array of user inputs, making digital interactions more efficient, accurate, and user-friendly.

## Solution Architecture

![Sample Image](/assets/solution_overview.png)

1.	User Input Reception: The user presents a question/query to the Conversational AI system.
2.	Initial LLM Evaluation: An LLM evaluates each question along with the chat history from the same session to determine its nature and which subject area it falls under (e.g., SQL, action, search, SME).
3.	Router Chain Activation:
    - If the question is identified with a subject, the Router Chain directs it to the corresponding Destination Chain.
    - The Default Chain handles queries that don't match specific subjects, providing insights through the Bedrock Model.
4.	Subject-Specific Routing:
    - SQL-related queries are sent to the SQL Destination Chain for database interactions.
    - Action-oriented questions trigger the Custom Lambda Destination Chain for executing operations.
    - Search-focused inquiries proceed to the RAG Destination Chain for information retrieval.
    - SME-related questions go to the SME/Expert Destination Chain for specialized insights.
5.	Destination Chain Processing: Each Destination Chain takes the input and executes the necessary models or functions:
    - SQL Chain uses [Amazon Athena](https://aws.amazon.com/athena) for executing queries.
    - RAG Chain utilizes [Amazon OpenSearch](https://aws.amazon.com/opensearch-service/serverless-vector-engine/) for semantic searches.
    - Custom Lambda Chain executes AWS Lambda functions for actions.
    - SME/Expert Chain provides insights via the Bedrock Model.
6.	Response Generation and Delivery: Responses from each Destination Chain are formulated into coherent insights by the LLM. These insights are then delivered to the user, completing the query cycle.


## Technical deep dive

![Technical Architecture](/assets/technical_architecture.png)

For detailed implementation instructions and setup steps, please refer to the guide linked [here](multi-route-chain-app/README.md)

## How to Use 

1. This is Ameer, who are you?
2. Can you query me max metrics for device 1001?
3. Can you search for the operating temperature range for this device?
4. As a physics SME, can you compare the max temperature with the operating temperature range and tell me what you think?
5. Okay, can you please shutdown this device?
6. Can you generate a summary about our conversation today?

![How to Use](/assets/conversationalAI-Recording-gif.gif)


Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0