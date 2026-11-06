# Setup and failure behavior

## Local emulator

On a machine with Docker, start LocalStack as in `.github/workflows/ci.yml`, install `requirements.txt`, and set `AWS_ACCESS_KEY_ID=test`, `AWS_SECRET_ACCESS_KEY=test`, and `AWS_DEFAULT_REGION=us-east-1`. Run `python -m unittest discover -s tests -p integration.py -v`. Start the MQTT broker shown in the workflow too. The test deploys the CloudFormation template to LocalStack and uses a real MQTT broker plus a test-only subscriber that forwards to SQS in place of the IoT rule. It checks SQS and S3. LocalStack community does not implement IoT Core, so this does not verify the real rule or device authentication. Stop the container afterwards. The CI uses an isolated container and does this cleanup automatically.

## AWS setup

Deploy `infra/template.yaml` in CloudFormation with IAM capability enabled. In IoT Core create a thing and active certificate, attach the certificate to the thing and attach a policy allowing `iot:Connect` for its client ID and `iot:Publish` for the `robots/status` topic. Download the private key and certificate once, obtain Amazon Root CA 1, and use the account's IoT data endpoint. Give the consumer SQS receive/delete/get attributes on the output queue and S3 list/get/put on the output bucket. Supply AWS credentials through the standard AWS credential chain. This template does not create device identities or consumer credentials. AWS resources may incur charges; remove the stack and empty its bucket when finished.

## Guarantees and limits

SQLite keeps unsent events across process restarts. A single publisher per database preserves local enqueue order. A failed connection or missing acknowledgement leaves the oldest event queued; retries can publish it twice if the acknowledgement was lost. QoS 1 and standard SQS are at-least-once, so the consumer uses a stable event ID as the S3 key. Duplicate copies overwrite the same object, not a second record. This assumes an ID always refers to the same immutable event. S3 writes precede SQS deletion, so a crash between those steps is safe to retry. Invalid messages are left for SQS to move to the dead-letter queue after five receives; operational monitoring and redrive are the operator's responsibility.

The health summary uses event observation time rather than arrival order. Robot clocks need to be synchronized, and an offline robot's last reported time does not prove it is currently online. The summary scans all event objects and is intended for a small fleet; a larger deployment needs an indexed, conditional last-seen store. There is no queue size limit or automatic retention, so monitor disk and bucket growth. The IoT rule has no error action configured, and broker acknowledgement alone does not guarantee the rule delivered to SQS; production use needs rule error handling and alarms. Authentication and real AWS routing are not validated by the emulator.
