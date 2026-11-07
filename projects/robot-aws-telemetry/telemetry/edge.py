"""Durable, ordered MQTT publisher for robot status."""
import argparse
import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone

TOPIC = 'robots/status'

class Outbox:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS outbox (seq INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL)')
        self.db.commit()

    def add(self, robot_id, status, observed_at=None):
        event = {'id': str(uuid.uuid4()), 'robot_id': robot_id, 'observed_at': observed_at or datetime.now(timezone.utc).isoformat(), 'status': status}
        self.db.execute('INSERT INTO outbox(payload) VALUES (?)', (json.dumps(event),))
        self.db.commit()
        return event

    def flush(self, publish):
        """Remove only after broker acknowledgement; stop at the first failure."""
        while True:
            row = self.db.execute('SELECT seq, payload FROM outbox ORDER BY seq LIMIT 1').fetchone()
            if row is None:
                return
            publish(TOPIC, row[1])
            self.db.execute('DELETE FROM outbox WHERE seq = ?', (row[0],))
            self.db.commit()

    def close(self):
        self.db.close()

class MqttPublisher:
    def __init__(self, host, port, client_id, ca=None, cert=None, key=None):
        import paho.mqtt.client as mqtt
        self.mqtt = mqtt
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if ca:
            import ssl
            context = ssl.create_default_context(cafile=ca)
            if cert and key: context.load_cert_chain(cert, key)
            context.set_alpn_protocols(['x-amzn-mqtt-ca'])
            self.client.tls_set_context(context)
        self.client.connect(host, port, keepalive=30)
        self.client.loop_start()

    def publish(self, topic, payload):
        info = self.client.publish(topic, payload, qos=1)
        if info.rc != self.mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError('MQTT publish failed: %s' % info.rc)
        info.wait_for_publish(timeout=10)
        if not info.is_published():
            raise TimeoutError('MQTT acknowledgement timed out')

    def close(self):
        self.client.disconnect()
        self.client.loop_stop()

def main():
    p = argparse.ArgumentParser(description='Queue one status and retry delivery until acknowledged')
    p.add_argument('--robot', required=True)
    p.add_argument('--status', required=True, help='JSON object, e.g. {"battery": 85}')
    p.add_argument('--db', default='outbox.sqlite3')
    p.add_argument('--host', required=True)
    p.add_argument('--port', type=int, default=8883)
    p.add_argument('--ca'); p.add_argument('--cert'); p.add_argument('--key')
    args = p.parse_args()
    status = json.loads(args.status)
    if not isinstance(status, dict):
        p.error('status must be a JSON object')
    if args.port == 8883 and not all((args.ca, args.cert, args.key)):
        p.error('TLS port 8883 requires --ca, --cert and --key')
    box = Outbox(args.db)
    box.add(args.robot, status)
    try:
        while True:
            publisher = None
            try:
                publisher = MqttPublisher(args.host, args.port, args.robot, args.ca, args.cert, args.key)
                box.flush(publisher.publish)
                break
            except (OSError, RuntimeError, TimeoutError) as exc:
                print('Delivery failed, retrying:', exc, flush=True)
                time.sleep(5)
            finally:
                if publisher:
                    publisher.close()
    finally:
        box.close()

if __name__ == '__main__':
    main()
