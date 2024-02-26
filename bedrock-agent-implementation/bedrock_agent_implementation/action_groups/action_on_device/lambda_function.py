import boto3
import os
from botocore.exceptions import ClientError

SENDER = os.getenv('SENDER')
RECIPIENT = os.getenv('RECIPIENT')

def lambda_handler(event, context):
    # Extract necessary information from the input event
    
    print(event)
    action_group = event['actionGroup']
    api_path = event['apiPath']
    query_parameters = event['parameters'][0]
    device_id = query_parameters['value']
    action = api_path
    print(action)
    print(device_id)

    ses_client = boto3.client('ses')
    # Customize the email based on the action and deviceID
    subject = f"Action Performed: {action} on Device {device_id}"
    body_text = f"Hello,\r\nThe device {device_id} has been {action}."
    body_html = f"""
    <html>
    <head></head>
    <body>
        <h1>Action Performed!</h1>
        <p>The device {device_id} has been {action}.</p>
    </body>
    </html>
    """
    charset = "UTF-8"

    httpStatusCode = 200
    response_body = None

    try:
        ses_client.send_email(
            Source=SENDER,
            Destination={
                'ToAddresses': [RECIPIENT],
            },
            Message={
                'Subject': {
                    'Charset': charset,
                    'Data': subject,
                },
                'Body': {
                    'Text': {
                        'Charset': charset,
                        'Data': body_text,
                    },
                    'Html': {
                        'Charset': charset,
                        'Data': body_html,
                    },
                },
            },
        )

    except ClientError as e:
        print(e.response['Error']['Message'])
        httpStatusCode = 500
        response_body = f"Error sending email: {e.response['Error']['Message']}"

    # Bedrock action group response format
    action_response = {
        "messageVersion": "1.0",
        "response": {
            'actionGroup': action_group,
            'apiPath': api_path,
            'httpMethod': event['httpMethod'],
            'httpStatusCode': httpStatusCode,
            'responseBody': response_body
        }
    }
 
    return action_response
