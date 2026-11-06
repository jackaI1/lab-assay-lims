import json
import tempfile
import unittest
from pathlib import Path
from telemetry.edge import Outbox
from telemetry.consumer import store, health, process_once

class FakeS3:
    def __init__(self): self.objects = {}
    def put_object(self, Bucket, Key, Body, **kwargs): self.objects[Key] = Body
    def get_paginator(self, name): return self
    def paginate(self, **kwargs): return [{'Contents': [{'Key': k} for k in self.objects]}]
    def get_object(self, Bucket, Key):
        import io
        return {'Body': io.BytesIO(self.objects[Key])}

class Tests(unittest.TestCase):
    def test_disconnect_restart_and_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'queue.db')
            box = Outbox(path)
            one = box.add('robot', {'battery': 1})
            two = box.add('robot', {'battery': 2})
            def fail(topic, payload): raise ConnectionError('offline')
            with self.assertRaises(ConnectionError): box.flush(fail)
            box.close()
            box = Outbox(path)
            received = []
            box.flush(lambda topic, payload: received.append(json.loads(payload)))
            self.assertEqual([one, two], received)
            box.flush(lambda *args: self.fail('queue should be empty'))
            box.close()

    def test_duplicates_and_out_of_order(self):
        s3 = FakeS3()
        with tempfile.TemporaryDirectory() as d:
            box = Outbox(str(Path(d) / 'q'))
            old = box.add('robot', {'battery': 80}, '2025-01-01T00:00:00+00:00')
            new = box.add('robot', {'battery': 60}, '2025-01-02T00:00:00+00:00')
            for event in (new, old, new): store(s3, 'bucket', event)
            self.assertEqual(len(s3.objects), 2)
            self.assertEqual(health(s3, 'bucket')['robot']['status'], {'battery': 60})
            box.close()

    def test_failed_storage_does_not_ack(self):
        class Queue:
            def receive_message(self, **kwargs): return {'Messages': [{'Body': '{}', 'ReceiptHandle': 'x'}]}
            def delete_message(self, **kwargs): raise AssertionError('must not delete')
        self.assertEqual(process_once(Queue(), FakeS3(), 'q', 'b', 0), 1)

if __name__ == '__main__': unittest.main()
