# robot-aws-telemetry

I built a robot status link to learn how the underlying idea works. This is a learning project.

The examples use generated robot readings and local service emulators.

## Try it

Python 3.9 or later is needed. From this folder:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
```

To send a real update, deploy the template in `infra/template.yaml` with CloudFormation, create an AWS IoT certificate and policy allowing the device to connect and publish to `robots/status`, and attach the policy to the certificate. Download the certificate, private key and Amazon Root CA 1. Find the IoT data endpoint in the AWS console. Keep keys outside this repository.

```sh
python -m telemetry.edge --robot desk-robot --status '{"battery": 85}' --host YOUR_IOT_ENDPOINT --ca /path/root-ca.pem --cert /path/device-cert.pem --key /path/private-key.pem
python -m telemetry.consumer consume --bucket YOUR_BUCKET --queue-url YOUR_QUEUE_URL
# In another terminal:
python -m telemetry.consumer health --bucket YOUR_BUCKET
```

The CloudFormation outputs provide the bucket and queue URL. The consumer needs AWS credentials permitting SQS receive/delete and S3 read/write. See [setup and failure behavior](docs/design.md) for emulator instructions, permissions, and limitations.

## Tests and limits

There are 2 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Retained project workflows: `robot-aws-telemetry-ci.yml`. Their commands use this folder and their triggers use its paths.
