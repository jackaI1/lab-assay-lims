# Verification notes

I record checks here after they run. The Android app is a new repository implementation; the existing regression suite belongs to its pinned bridge dependency.

The local sandbox uses unchanged bridge commit `c538aa220a40e0e322599d4edccc5267971061a0`. It adds an in-memory fictional upstream, two explicit encounters, and 18 observations: heart rate, temperature and oxygen, sampled three times per encounter. Its successful report accounts for all 18 readings, with zero unassigned or excluded.

- The pinned bridge's existing suite: **89 passed** locally.
- Sandbox integration: **4 passed** locally, checking consent, report values and counts, refresh rotation, session expiry, state/code replay, denied access, wrong-patient rejection and revoked refresh.
- Android debug APK build and lint: **passed** locally.
- JUnit/Robolectric: **32 passed**, covering 14 parsing cases, 8 cache cases, 6 HTTP/configuration cases and 4 chart cases.
- Instrumented tests on a local Android 15 / API 35 ARM64 emulator: **6 passed** (5 Compose screen checks and 1 full bridge journey). The journey approves consent, reads all three vital signs, checks automatic token renewal, reopens a saved snapshot with no session, expires the server session, retains the saved readings and clears the cache on sign-out.

The sandbox proves the app-to-bridge contract and the bridge's SMART token lifecycle against a simulated authorization/FHIR upstream. It does not prove a live hospital connection or Android login to OpenEMR's default self-signed TLS setup. Real OpenEMR setup and that certificate boundary are described in `setup.md`.

I inspected the [emulator screenshot](screenshots/vitals.png) for readable labels, charts, units and source-value lists. CI also collects this screenshot from the instrumented journey.
