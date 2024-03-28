# Building an Advanced Conversational AI Assistant

## Content
- [Building an Advanced Conversational AI Assistant](#building-an-advanced-conversational-ai-assistant)
  - [Content](#content)
  - [Overview](#overview)
  - [Solutions](#solutions)
    - [Solution 1: Agents for Bedrock implementation](#solution-1-agents-for-bedrock-implementation)
    - [Solution 2: Open source langchain implementation](#solution-2-open-source-langchain-implementation)
  - [Deployment Guide](#deployment-guide)
  - [Demo](#demo)

## Overview

This repository explores the transformative potential of generative AI assistants. It assesses various AI assistant implementation strategies, including open-source options like **LangChain** and proprietary solutions like the **Amazon Bedrock Agent**. We outline the creation of a Conversational AI assistant designed to intelligently direct user inputs towards the most suitable chatbot functionality including:

- **Database Queries**: Explains how to fetch and present data from structured databases in direct response to user queries, enabling the AI to provide precise information as needed.
- **Semantic Searches**: Demonstrates advanced semantic search capabilities within a vector index, enhancing the AI's ability to understand and retrieve relevant information based on the nuances of conversation context.
- **Custom Tasks via Lambda Functions**: Offers insights into executing specific tasks requested by users, ranging from data manipulation to initiating complex workflows, showcasing the AI's adaptability to varied user needs.
- **Specialized Conversations**: Details engaging in specialized dialogues and performing distinct tasks, ensuring the AI can handle a wide array of user intents with high precision.
- **Natural Conversational Flow**: Focuses on maintaining a seamless and natural dialogue, making interactions feel more intuitive and human-like.

To highlight the benefits of generative AI, the repository presents a use case of an IoT operations AI bot in manufacturing environments. This Conversational AI bot can leverage LLMs and RAG to generate SQL queries, fetch relevant data from databases, and provide clear responses about the status or performance of connected devices. This capability enables proactive maintenance and ensures continuous production flow, demonstrating the transformative potential of generative AI in optimizing industrial operations.

## Solutions

### Solution 1: Agents for Bedrock implementation

![bedrock_solution](bedrock-agent-implementation/assets/bedrock_agent_architecture.png)

Bedrock Agent and Knowledge Base can be used to build and deploy Conversational AI with complex routing use cases. It provides a strategic advantage by simplifying infrastructure management, enhancing scalability, improving security, and alleviate undifferentiated heavy lifting.    

Jump to [bedrock-agent-implementation](bedrock-agent-implementation/README.md) for more details.

### Solution 2: Open source langchain implementation

![langchain_architecture](langchain-multi-route-implementation/assets/technical_architecture_langchain_implementation.png)

LangChain is an open-source framework that simplifies building Conversational AI by allowing easy integration of Large Language Models for specific needs. It offers a cost-effective way to develop AI applications quickly, with community support for troubleshooting and improvements. 

Jump to [langchain-multi-route-implementation](langchain-multi-route-implementation/README.md) for more details.

## Deployment Guide

For a comprehensive step-by-step deployment guide, please refer to the detailed solution README file:
 - [bedrock-agent-implementation](bedrock-agent-implementation/README.md#setup)
 - [langchain-multi-route-implementation](langchain-multi-route-implementation/README.md#setup)

## Demo

```
1. This is Ameer, who are you?
2. Can you query the max metrics for device 1001?
3. Can you search for the operating temperature range for this device?
4. As a physics SME, can you compare the max temperature with the operating temperature range and tell me what you think?
5. Okay, can you please shutdown this device?
6. Can you generate a summary about our conversation today?
```

![How to Use](/assets/conversationalAI-Recording-gif.gif)


Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0