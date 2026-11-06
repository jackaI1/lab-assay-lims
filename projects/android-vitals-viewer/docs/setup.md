# Running the fictional visits

I use Java 17, Android SDK platform 35, build tools 35.0.0 and the checked-in Gradle wrapper. Android Studio can install the SDK. For command-line builds, set `JAVA_HOME` and `ANDROID_HOME` to those installations; `adb` is in `$ANDROID_HOME/platform-tools`.

## Local sandbox

After the README setup, the emulator uses `http://localhost:8000` and patient `11111111-1111-4111-8111-111111111111`. `adb reverse` makes the emulator's localhost reach my Mac's server. The server must bind only to loopback. No passwords or service accounts are required. The sample has two visits and three readings for each of three vitals in each visit.

The sandbox installs an exact bridge commit from its public repository. It supplies a fictional SMART/FHIR upstream in memory using HTTPX, an HTTP client library, but uses the unchanged bridge login, callback, token refresh, synthetic-patient checks and visit-report routes. Consent is a link rather than a user account. It is a protocol sandbox, not an identity provider or full SMART certification test.

The sandbox tokens expire after 15 seconds. Wait six seconds after a successful load, then tap Refresh. The bridge renews the token before its expiry. This command reports how often renewal happened without revealing credentials:

```sh
curl --fail http://localhost:8000/sandbox/status
```

To expire all sandbox sessions, then test the app's recovery message:

```sh
curl --fail -X POST http://localhost:8000/sandbox/expire
```

Tap Refresh. The previous charts remain with the saved timestamp and a sign-in action. To test an unreachable bridge, stop its terminal with Ctrl-C and tap Refresh before closing the app. Reopening the app still loads its saved report. Start the sandbox again and sign in to recover.

## Existing OpenEMR bridge

Follow the [bridge's OpenEMR instructions](https://github.com/jackaI1/fhir-emr-bridge/blob/main/docs/integration.md). Its registered application, client secret and token refresh stay on the server. Use its normal localhost callback URL and one worker; do not place credentials in the Android build. Create a fictional patient using `POST /openemr/demo` after signing in through the bridge, and copy its returned patient UUID into the app.

If the bridge and OpenEMR are on ports 8000 and 9300:

```sh
adb reverse tcp:8000 tcp:8000
adb reverse tcp:9300 tcp:9300
```

Enter the exact bridge origin used by its callback (for example `http://127.0.0.1:8000`) and the new patient UUID. Sign in and approve access. The app calls `GET /openemr/patients/{uuid}/visits`; the bridge authenticates the request and reads the FHIR records. This fixture has one heart-rate and one temperature value, so those charts contain one point. It has no SpO₂ value. More values appear only if the fictional source actually contains them.

Android correctly rejects untrusted self-signed certificates, including OpenEMR's generated demo certificate. I do not bypass that validation. For an interactive Android check, serve OpenEMR with a locally trusted certificate installed on the emulator as a system trust anchor, or use a properly trusted HTTPS endpoint and matching bridge configuration. The no-account local sandbox is the reproducible default; I do not claim a verified Android-to-OpenEMR login against a self-signed deployment.

Stop the bridge with Ctrl-C and the OpenEMR containers with the bridge's documented `docker compose ... down -v --remove-orphans`. Remove both adb reversals. HTTPS origins are supported by the app; cleartext HTTP is limited to localhost and 127.0.0.1. No certificate errors are ignored.

## Run the checks

```sh
uv run --no-project pytest -q tests
./gradlew --no-daemon assembleDebug testDebugUnitTest lintDebug
bash scripts/instrumented.sh
```

The last command expects a running emulator and a free port 8000. It owns a sandbox child process, prints its PID/start time, forwards the port, runs connected UI tests, and removes the forwarding and stops its server in an exit trap. It never stops someone else's server. The CI action owns and closes its emulator. For local work, close the emulator I opened through Android Studio after checking the app.
