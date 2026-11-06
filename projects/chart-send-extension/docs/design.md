# Design and limits

I keep this demonstration on loopback, using only synthetic records. It helps me test moving a selection from a chart to a receiver without keeping an extra copy of the files in extension storage.

## Transfer boundary

The content script runs in OpenEMR document frames. It checks the exact origin and path, a numeric patient ID and native `document&view` links with matching patient IDs. It adds checkboxes in a shadow root so OpenEMR's styles do not change the controls. A mutation observer finds document links added as the tree renders. The send button locks the selection during the transfer.

The worker accepts messages only from this extension and an actual tab, validates the sender frame URL, rejects empty or duplicate selections, and constructs the download URLs itself. A message cannot supply an arbitrary URL. The worker uses the signed-in OpenEMR session only for chart downloads. Receiver calls omit credentials. Neither the token nor the document contents are persisted. A new worker can handle the next message without recovering document state.

The official image serves OpenEMR at its web root. `demo/chart-send.conf` adds an Apache alias at `/openemr` so the extension can use a narrow application path without changing OpenEMR code.

The manifest allows only HTTP on `127.0.0.1`. Its content-script path is limited to `/openemr/controller.php`; runtime checks also require port 8080 and a document screen. Host permission covers the loopback host; application validation narrows outgoing ports. This does not expose permission to remote websites or `localhost`.

The whole send has a 20-second deadline. Downloads are read as bounded streams, including responses without Content-Length. HTML login pages, empty files, unsupported types, redirects, forbidden documents and files over 1 MiB are refused. The receiver separately checks document shapes, MIME types and base64 length. File types are declared types, not a malware scan.

## Receiver and retries

`POST /token` issues a random 32-byte token with a 30-second lifetime. `POST /send` consumes it, even if the subsequent batch validation fails. The token is sent as a Bearer header, never in a URL. Browser origins other than extension origins are refused, and the receiver binds only to `127.0.0.1`.

The receiver consumes a batch in memory and discards its file contents. A successful response has a receipt ID and document count. `GET /health` shows readiness and a receipt count, without exposing document names or patient IDs. This is a working receiving endpoint, not a document archive or an integration with a commercial service.

The panel keeps a request ID while a selection is unchanged. Retrying with that ID and identical contents returns the same receipt. A changed body with the same ID returns 409 instead of silently accepting a different batch. Toggling a selection creates a new request ID. Receipt metadata contains a digest, count, receipt ID and expiry; it contains no document contents. Tokens and receipts are bounded to 1,000 entries and expired entries are removed on POST requests. No database or disk archive is created.

Deduplication lasts only for the receiver's current process and 10-minute retention window. Restarting the receiver, reloading the chart, changing the selection or switching receivers can create another accepted send. I expose retries to the user rather than automatically repeating ambiguous sends. All batches are accepted together after validation.

## What this does not secure

A loopback token endpoint is not user authentication. Other local software can obtain a token. The extension checks the chart context, while OpenEMR remains responsible for authorizing its document downloads. The demo administrator can access both fictional patients. This is not a claim of clinical safety, regulatory compliance, malware protection or production readiness.

The pinned OpenEMR image is for an isolated demo, not a production deployment. Ports bind to loopback and the credentials are public demo values. The database should never contain real records. Seeding is restricted to an empty database and cleanup removes the disposable Docker volumes.

## Reproducibility and cleanup

`npm ci` uses the committed lockfile. `npm run build` bundles local scripts into `dist`; no remote script runs inside the extension. Playwright launches its bundled Chromium in a temporary profile with the real unpacked extension loaded. Tests close that entire context and both owned pages, stop their in-process servers, and delete the profile, including setup failures. Resource metadata is written under ignored `test-results/`.

CI runs the fixture suite and actual OpenEMR suite as separate jobs. Each job uses one browser context. The real suite seeds two fictional patients and three text documents, signs in through the app and compares the receiver's digest against the expected file bytes. An always-run Compose teardown removes containers and volumes. Diagnostic logs are bounded and artifacts contain only fictional demo data.

I used the [OpenEMR document controller](https://github.com/openemr/openemr/blob/v7_0_3/controllers/C_Document.class.php), [Chrome match-pattern documentation](https://developer.chrome.com/docs/extensions/develop/concepts/match-patterns) and [Playwright's extension testing guide](https://playwright.dev/docs/chrome-extensions) for the integration boundaries.
