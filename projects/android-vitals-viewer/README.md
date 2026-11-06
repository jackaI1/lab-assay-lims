# android-vitals-viewer

I built a phone app for comparing fictional patients' measurements to learn how the underlying idea works. This is a learning project.

## Try it

I use the included local sandbox first. It has two fictional visits with 18 measurements, a consent page and short-lived access so I can exercise sign-in and renewal without an account. It runs the actual [fhir-emr-bridge](https://github.com/jackaI1/fhir-emr-bridge) service with a simulated record server. It does not contact a real patient database.

With [Android Studio](https://developer.android.com/studio), Java 17 and [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```sh
uv venv --python 3.12
uv pip install -r sandbox/requirements.lock
uv run --no-project uvicorn sandbox.server:app --host 127.0.0.1 --port 8000 --no-access-log
```

Leave that terminal open. Open this folder in Android Studio, let it install SDK 35, and run `app` on an Android 8.0 or newer emulator. In another terminal, connect the emulator to the local service:

```sh
adb reverse tcp:8000 tcp:8000
```

Keep the app's default bridge URL and fictional patient UUID. Tap **Sign in with SMART on FHIR** (the record system's permission process), then **Approve fictional records**. Choose either visit and scroll to the three charts. The values are also written underneath each chart. Cancel or deny returns no records.

Stop the sandbox with Ctrl-C when finished, then run `adb reverse --remove tcp:8000`. [The setup guide](docs/setup.md) includes command-line builds, testing session expiry, and connecting to my existing OpenEMR demo.

## How the parts fit

SMART on FHIR is the permission process used to sign in and approve record access. FHIR is the shared format for medical records. My existing bridge handles that process, holds the access and refresh tokens, and returns a report containing only its fixed fictional patient records. The Android app holds the bridge's session cookie in memory; it never receives those tokens or a client secret.

I wrote the app in Kotlin with Jetpack Compose, Android's interface toolkit. Room, an Android database library, stores one validated report per bridge and patient. A successful refresh replaces the whole snapshot so removed readings do not linger. A network error or rejected report keeps the previous copy. The screen labels that copy with its saved time instead of presenting it as a fresh result.

[Design and boundaries](docs/design.md) explain the files, units, cache, and sign-in decisions. This is a local demonstration with fictional records, not a clinical tool. Its embedded sign-in page reuses the bridge's browser-bound cookie flow. A deployed app would need an external-browser handoff and additional controls before handling real records.

## Tests and limits

I kept 5 files of test code and supporting test helpers in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



The relocated workflow did not complete successfully within the migration batch. Local test sources remain available.

No project-specific GitHub Actions workflow was retained. The local test sources remain in this folder.
