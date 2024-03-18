"""Custom chain action lambda to send email using SES"""
import os
import json
import boto3
from botocore.exceptions import ClientError

SENDER = os.getenv('SENDER')
RECIPIENT = os.getenv('RECIPIENT')


def lambda_handler(event, _):
    """Lambda handler"""
    # If event is a string, attempt to load it as JSON
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'body': 'Invalid input format. Expected a JSON object.'
            }

    # Extract deviceID and Action from the event
    device_id = event.get('deviceID')
    action = event.get('Action')

    # Print for debugging
    print(f"Device ID: {device_id}, Action: {action}")

    # Change the region if necessary
    ses_client = boto3.client('ses', region_name='us-east-1')

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
        return {
            'statusCode': 500,
            'body': f"Error sending email: {e.response['Error']['Message']}"
        }

    print(f"{device_id} has been {action}")
    return {
        'statusCode': 200,
        'body': f"Device:{device_id} has been {action}"
    }
