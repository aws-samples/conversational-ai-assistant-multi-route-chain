import streamlit as st
import boto3
import os
import random
import string

BEDROCK_AGENT_ALIAS = os.getenv('BEDROCK_AGENT_ALIAS')
BEDROCK_AGENT_ID = os.getenv('BEDROCK_AGENT_ID')

client = boto3.client('bedrock-agent-runtime')

def format_retrieved_references(references):
    # Extracting the text and link from the references
    for reference in references:
        content_text = reference.get("content", {}).get("text", "")
        s3_uri = reference.get("location", {}).get("s3Location", {}).get("uri", "")

        # Formatting the output
        formatted_output = "Reference Information:\n"
        formatted_output += f"Content: {content_text}\n"
        formatted_output += f"S3 URI: {s3_uri}\n"

        return formatted_output


def process_stream(stream):
    try:
        # print("Processing stream...")
        trace = stream.get("trace", {}).get("trace", {}).get("orchestrationTrace", {})

        if trace:
            # print("This is a trace")
            knowledgeBaseInput = trace.get("invocationInput", {}).get(
                "knowledgeBaseLookupInput", {}
            )
            if knowledgeBaseInput:
                print(
                    f'Looking up in knowledgebase: {knowledgeBaseInput.get("text", "")}'
                )
            knowledgeBaseOutput = trace.get("observation", {}).get(
                "knowledgeBaseLookupOutput", {}
            )
            if knowledgeBaseOutput:
                retrieved_references = knowledgeBaseOutput.get(
                    "retrievedReferences", {}
                )
                if retrieved_references:
                    print("Formatted References:")
                    return format_retrieved_references(retrieved_references)

        # Handle 'chunk' data
        if "chunk" in stream:
            print("This is the final answer:")
            text = stream["chunk"]["bytes"].decode("utf-8")
            return text

    except Exception as e:
        print(f"Error processing stream: {e}")
        print(stream)

def session_generator():
    # Generate random characters and digits
    digits = ''.join(random.choice(string.digits) for _ in range(4))  # Generating 4 random digits
    chars = ''.join(random.choice(string.ascii_lowercase) for _ in range(3))  # Generating 3 random characters
    
    # Construct the pattern (1a23b-4c)
    pattern = f"{digits[0]}{chars[0]}{digits[1:3]}{chars[1]}-{digits[3]}{chars[2]}"
    print("Session ID: " + str(pattern))

    return pattern

def main():
    st.title("Conversational AI - Plant Technician")

    # Initialize the conversation state
    if 'conversation' not in st.session_state:
        st.session_state.conversation = []
    # Initialize the agent session id
    if 'session_id' not in st.session_state:
        st.session_state.session_id = session_generator()

    # Taking user input
    user_prompt = st.text_input("Message:")

    if user_prompt:
        try:
            # Add the user's prompt to the conversation state
            st.session_state.conversation.append({'user': user_prompt})

            # Format and add the answer to the conversation state
            response = client.invoke_agent(
                agentId=BEDROCK_AGENT_ID,
                agentAliasId=BEDROCK_AGENT_ALIAS,
                sessionId=st.session_state.session_id,
                endSession=False,
                inputText=user_prompt
            )
            results = response.get("completion")
            answer = ""
            for stream in results:
                answer += process_stream(stream)
            st.session_state.conversation.append(
                {'assistant': answer})

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
