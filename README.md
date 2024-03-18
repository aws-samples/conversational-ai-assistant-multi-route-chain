# Building an Advanced Conversational AI Assistant

## Content
- [Building an Advanced Conversational AI Assistant](#building-an-advanced-conversational-ai-assistant)
  - [Content](#content)
  - [Overview](#overview)
  - [Solution Architecture](#solution-architecture)
    - [Solution 1: Open source langchain implementation](#solution-1-open-source-langchain-implementation)
    - [Solution 2: Agents for Bedrock implementation](#solution-2-agents-for-bedrock-implementation)
  - [Demo](#demo)

## Overview

In this repository, we explore the transformative impact of AI assistants in manufacturing, where they empower technicians to efficiently oversee and maintain machinery. A simple command to check a device's status triggers the system to employ large language models (LLMs) for generating SQL queries, fetching relevant data, and delivering clear responses. For complex queries, the system switches to a Retrieval-Augmented Generation (RAG) mode, leveraging LLMs and embeddings to mine deeper insights from extensive knowledge bases. Actionable requests activate custom scripts, facilitating smooth operations and maintaining continuous production flow. Each interaction enhances the assistant's conversational skills, making it more adept over time.

Additionally, this repository assesses various AI assistant implementation strategies, including open-source options like LangChain and proprietary solutions like the Amazon Bedrock agent, discussing the benefits and drawbacks of each approach. We outline the creation of a Conversational AI assistant designed to intelligently direct user inputs towards the most suitable chatbot functionality including:

- **Database Queries**: Explains how to fetch and present data from structured databases in direct response to user queries, enabling the AI to provide precise information as needed.
- **Semantic Searches**: Demonstrates advanced semantic search capabilities within a vector index, enhancing the AI's ability to understand and retrieve relevant information based on the nuances of conversation context.
- **Custom Tasks via Lambda Functions**: Offers insights into executing specific tasks requested by users, ranging from data manipulation to initiating complex workflows, showcasing the AI's adaptability to varied user needs.
- **Specialized Conversations**: Details engaging in specialized dialogues and performing distinct tasks, ensuring the AI can handle a wide array of user intents with high precision.
- **Natural Conversational Flow**: Focuses on maintaining a seamless and natural dialogue, making interactions feel more intuitive and human-like.

This repository serves as a comprehensive guide for developers looking to build sophisticated Conversational AI systems that can intelligently navigate and respond to a wide array of user inputs, making digital interactions more efficient, accurate, and user-friendly.

## Solution Architecture

This repository provides the following solutions. 

### Solution 1: Open source langchain implementation

Organizations can utilize Amazon Bedrock and Amazon SageMaker JumpStart to access a wide variety of Large Language Models (LLMs), with LangChain serving as the interface that seamlessly integrates these models into their applications. LangChain is an open-source framework that simplifies building Conversational AI by allowing easy integration of Large Language Models for specific needs. It offers a cost-effective way to develop AI applications quickly, with community support for troubleshooting and improvements. 

Jump to [langchain-multi-route-implementation](langchain-multi-route-implementation/README.md) for detailed implementation and set up.

### Solution 2: Agents for Bedrock implementation

Bedrock Agent and Knowledge Base can be used to build and deploy Conversational AI with complex routing use cases. It provides a strategic advantage by simplifying infrastructure management, enhancing scalability, improving security, and alleviate undifferentiated heavy lifting.  

Jump to [bedrock-agent-implementation](bedrock-agent-implementation/README.md) for detailed implementation and set up.

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