"""Exercise MQTT and LocalStack SQS/S3 with a test-only IoT rule bridge."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
import boto3
import paho.mqtt.client as mqtt
from telemetry.edge import Outbox, MqttPublisher
from telemetry.consumer import health, process_once

ENDPOINT = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')

class Integration(unittest.TestCase):
    def test_pipeline(self):
        cf = boto3.client('cloudformation', endpoint_url=ENDPOINT)
        sqs = boto3.client('sqs', endpoint_url=ENDPOINT)
        s3 = boto3.client('s3', endpoint_url=ENDPOINT)
        cf.create_stack(StackName='robot-telemetry', TemplateBody=Path('infra/template.yaml').read_text(), Capabilities=['CAPABILITY_IAM'])
        cf.get_waiter('stack_create_complete').wait(StackName='robot-telemetry', WaiterConfig={'Delay': 3, 'MaxAttempts': 40})
        outputs = {x['OutputKey']: x['OutputValue'] for x in cf.describe_stacks(StackName='robot-telemetry')['Stacks'][0]['Outputs']}
        # LocalStack community does not implement IoT Core. This subscriber
        # emulates the rule's MQTT-to-SQS action, not IoT authentication.
        import threading
        ready = threading.Event()
        received = []
        bridge = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='test-rule')
        def connected(client, userdata, flags, reason, properties):
            client.subscribe('robots/status', qos=1)
        def subscribed(client, userdata, mid, reasons, properties): ready.set()
        def message(client, userdata, msg):
            sqs.send_message(QueueUrl=outputs['QueueUrl'], MessageBody=msg.payload.decode())
            received.append(msg.payload)
        bridge.on_connect = connected
        bridge.on_subscribe = subscribed
        bridge.on_message = message
        bridge.connect('localhost', 1883)
        bridge.loop_start()
        try:
            self.assertTrue(ready.wait(10))
            with tempfile.TemporaryDirectory() as directory:
                box = Outbox(str(Path(directory)/'queue.db'))
                old = box.add('demo', {'battery': 90}, '2025-01-01T00:00:00+00:00')
                new = box.add('demo', {'battery': 80}, '2025-01-02T00:00:00+00:00')
                with self.assertRaises(ConnectionError): box.flush(lambda *args: (_ for _ in ()).throw(ConnectionError('offline')))
                publisher = MqttPublisher('localhost', 1883, 'integration')
                try:
                    box.flush(publisher.publish)
                    publisher.publish('robots/status', json.dumps(old))
                    deadline = time.time() + 15
                    while len(received) < 3 and time.time() < deadline: time.sleep(.1)
                    self.assertEqual(len(received), 3)
                finally:
                    publisher.close(); box.close()
            deadline = time.time() + 30
            keys = []
            while time.time() < deadline:
                process_once(sqs, s3, outputs['QueueUrl'], outputs['Bucket'], wait=1)
                keys = s3.list_objects_v2(Bucket=outputs['Bucket'], Prefix='events/').get('Contents', [])
                if len(keys) == 2 and sqs.get_queue_attributes(QueueUrl=outputs['QueueUrl'], AttributeNames=['ApproximateNumberOfMessages'])['Attributes']['ApproximateNumberOfMessages'] == '0': break
            self.assertEqual(len(keys), 2)
            self.assertEqual(health(s3, outputs['Bucket'])['demo']['status'], new['status'])
        finally:
            bridge.disconnect(); bridge.loop_stop()

if __name__ == '__main__': unittest.main()
