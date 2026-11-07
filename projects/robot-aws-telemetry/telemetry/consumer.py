"""Persist SQS events under stable S3 keys and derive last-seen summaries."""
import argparse
import json
import re
from datetime import datetime, timezone

SAFE = re.compile(r'^[A-Za-z0-9_-]{1,128}$')

def validate(event):
    import uuid
    if not isinstance(event, dict) or not SAFE.fullmatch(event.get('robot_id', '')):
        raise ValueError('invalid robot_id')
    event_id = event.get('id', '')
    if str(uuid.UUID(event_id)) != event_id:
        raise ValueError('invalid id')
    timestamp = datetime.fromisoformat(event['observed_at'].replace('Z', '+00:00'))
    if timestamp.tzinfo is None or not isinstance(event.get('status'), dict):
        raise ValueError('invalid timestamp or status')
    return timestamp.astimezone(timezone.utc)

def store(s3, bucket, event):
    validate(event)
    key = 'events/%s/%s.json' % (event['robot_id'], event['id'])
    # Stable key makes redelivery overwrite the same object, including after a crash.
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(event, sort_keys=True).encode(), ContentType='application/json')
    return key

def process_once(sqs, s3, queue_url, bucket, wait=10):
    messages = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=wait).get('Messages', [])
    for message in messages:
        try:
            event = json.loads(message['Body'])
            store(s3, bucket, event)
        except (ValueError, KeyError, TypeError) as exc:
            # Leave malformed messages for the queue's dead-letter policy.
            print('Invalid event:', exc, flush=True)
            continue
        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message['ReceiptHandle'])
    return len(messages)

def health(s3, bucket):
    result = {}
    pages = s3.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix='events/')
    for page in pages:
        for item in page.get('Contents', []):
            event = json.loads(s3.get_object(Bucket=bucket, Key=item['Key'])['Body'].read())
            timestamp = validate(event)
            robot = event['robot_id']
            if robot not in result or timestamp > result[robot][0]:
                result[robot] = (timestamp, event)
    return {robot: {'last_seen': value[0].isoformat(), 'status': value[1]['status']} for robot, value in sorted(result.items())}

def main():
    import boto3
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['consume', 'health'])
    p.add_argument('--bucket', required=True); p.add_argument('--queue-url')
    p.add_argument('--endpoint-url', help='LocalStack endpoint; omit for AWS')
    args = p.parse_args()
    s3 = boto3.client('s3', endpoint_url=args.endpoint_url)
    if args.command == 'health':
        print(json.dumps(health(s3, args.bucket), indent=2))
    else:
        if not args.queue_url: p.error('--queue-url is required for consume')
        sqs = boto3.client('sqs', endpoint_url=args.endpoint_url)
        while True: process_once(sqs, s3, args.queue_url, args.bucket)

if __name__ == '__main__': main()
