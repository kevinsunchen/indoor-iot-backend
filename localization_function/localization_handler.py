from __future__ import print_function
import boto3
import localize_utils

def handle_request(event, context):
    for record in event["Records"]:
        print(record)
        
    return "localization_handler finished running" + "\n"