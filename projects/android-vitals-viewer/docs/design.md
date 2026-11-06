# Reading the app

I keep the native side small so I can trace a measurement from a bridge response to the screen.

| File | Responsibility |
| --- | --- |
| `VisitReport.kt` | Parse the bridge's visit report, retain source units and status, reject different patients, and compute time-spaced chart points. |
| `BridgeApi.kt` | Call the bridge with its opaque session cookie, refuse redirects and unsafe origins, bound response size, and classify expired sessions. |
| `Cache.kt` | Define the Room database and replace a snapshot only after its complete response validates. |
| `VitalsViewModel.kt` | Load saved data, coordinate sign-in and refresh, keep session state in memory, and report stale data and recovery actions. |
| `LoginScreen.kt` | Reuse the bridge's consent flow in a WebView, then pass its session cookie to the native HTTP client. |
| `MainActivity.kt` | Render the Compose visit selector, charts, source values and accessible text. |
| `sandbox/server.py` | Run the pinned, unchanged bridge against fictional SMART and FHIR responses. |

## Permission and expiry

The bridge discovers the authorization and token endpoints and performs authorization-code exchange with PKCE. PKCE is a one-use proof that binds the returned code to the process that started sign-in. Its existing implementation checks browser-bound state, consumes it once, rotates refresh tokens when needed, serializes concurrent refreshes and removes rejected sessions. This repository's integration tests exercise those paths through the actual bridge, including denied consent, wrong state, replay, revoked refresh and logout.

The Android app does not implement a second token store. After the bridge callback finishes, it reads the HttpOnly bridge session cookie through Android's native CookieManager and uses it for the report request. No JavaScript interface reads the cookie, and no client secret or access/refresh token reaches the APK. The callback by itself is not evidence of access: the bridge must accept the next data request. A 401/403 clears the native session and leaves the saved report labelled as saved. An upstream 502 preserves the cache and offers retry or sign-in, since the bridge may translate a rejected refresh into an upstream error before a later request returns 401.

The WebView is destroyed and its cookies cleared after use or cancellation. It blocks file/content access, third-party cookies and non-web navigations, and never ignores TLS errors. JavaScript is enabled for the existing OpenEMR consent pages. This embedded browser is appropriate only for this fictional local demonstration; a production native flow should use the system browser with a bridge-to-app handoff rather than copy a browser cookie. The existing bridge has no such handoff route. An app process restart deliberately requires a new sign-in, while non-sensitive connection settings and fictional cached reports persist.

## Saved reports and chart boundaries

Room keys each snapshot by normalized bridge origin and patient UUID. A validated response replaces one row atomically. I keep the original JSON, including absent and excluded results, so offline parsing follows the same rules as online parsing. It avoids partial multi-table refreshes and naturally removes readings that disappear from the source. Backup is disabled. Sign-out clears all snapshots even when the bridge is unreachable; the app explains when it could not invalidate the remote session.

Only the bridge's `synthetic_only: true` report for the requested patient is accepted. The bridge independently verifies the fictional patient's fixed name and date of birth. The Android parser requires unique encounter and observation IDs. It plots LOINC-coded heart rate, temperature and oxygen readings with recognized UCUM units, both standard ways to identify a measurement and its unit. It preserves Fahrenheit/Celsius on separate charts. The screen gives UCUM codes friendly labels: `/min` becomes bpm, `Cel` becomes °C and `[degF]` becomes °F, without changing the numbers. Numeric zero is valid; strings, absent values, unknown units, comparator quantities, unknown/cancelled/error statuses, components, modifier extensions and missing timestamps are not plotted as exact numbers. Preliminary values remain visibly labelled. I rely on the bridge's checked visit links; unassigned and excluded records appear as counts instead of being guessed into a visit.

The chart places samples by elapsed time and lists every supported reading below it for accessibility. An axis caption gives the value range and UTC time interval. A single point does not imply a trend. This app does not normalize units, deduplicate clinical revisions, interpret diagnoses, detect dangerous thresholds or replace a medical record system. It has no real patient input or cloud backend.
