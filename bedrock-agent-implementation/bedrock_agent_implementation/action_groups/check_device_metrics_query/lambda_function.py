import boto3
import json
import time
import os

def lambda_handler(event, context):
    # Extract necessary information from the input event
    
    print(event)
    action_group = event['actionGroup']
    api_path = event['apiPath']
    query_parameters = event['parameters'][0]
    sql_query = query_parameters['value']
    
    print(sql_query)

    # Specify your Athena database and output location
    database = os.getenv('ATHENA_DATABASE')  # Replace with your Athena database name
    output_location = os.getenv('ATHENA_OUTPUT_LOCATION')  # Replace with your Athena output location
    # Create Athena client
    athena_client = boto3.client('athena')

    # Run the Athena query
    response = athena_client.start_query_execution(
        QueryString=sql_query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': output_location}
    )

    # Get the query execution ID
    query_execution_id = response['QueryExecutionId']
    print(query_execution_id)

    # Poll for the query execution status
    while True:
        query_status = athena_client.get_query_execution(QueryExecutionId=query_execution_id)['QueryExecution']['Status']['State']
        print(query_status)
        if query_status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        
        time.sleep(5)  # Wait for 5 seconds before checking again

    # Get the query results
    results = athena_client.get_query_results(QueryExecutionId=query_execution_id)

    # Extract and return the results
    columns = [col_info['Name'] for col_info in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = [dict(zip(columns, row['Data'])) for row in results['ResultSet']['Rows'][1:]]
    
    print(json.dumps(results))
    print(json.dumps(data))

    response_body = {
        'application/json': {
            'body': json.dumps(data)
        }
    }
    
    # Bedrock action group response format
    action_response = {
        "messageVersion": "1.0",
        "response": {
            'actionGroup': action_group,
            'apiPath': api_path,
            'httpMethod': event['httpMethod'],
            'httpStatusCode': 200,
            'responseBody': response_body
        }
    }
 
    return action_response
