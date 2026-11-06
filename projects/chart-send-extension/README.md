# chart-send-extension

I built a one-click chart sender to learn how the underlying idea works. This is a learning project.

## Try it

I use Node.js 24, Docker with Compose, and Chrome with developer mode enabled. The first OpenEMR startup can take several minutes.

```sh
npm ci
npm run build
docker compose up -d
node scripts/wait-openemr.mjs
npm run demo:seed
npm run receiver
```

1. Open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked**, and choose this project's `dist` folder.
2. Open <http://127.0.0.1:8080/openemr/>. Sign in with the local demo account: `admin` / `fictional-demo-only`.
3. Find **Fictional River** in Patients, open the chart, and choose **Documents**. Select `fictional-lab.txt` or `fictional-referral.txt` in the Chart Send panel, then click **Send selected**.
4. Look for **Sent 1 document** and a receipt. To change the receiver, open this extension's **Details > Extension options**. I allow only `http://127.0.0.1:4318` and `http://127.0.0.1:4319`.

The second seeded patient, Fictional Lake, has a different document. I keep that record separate when checking that River's selection stays in River's chart. The seed command refuses to run when the database already contains patients.

To see a retry, stop the receiver with Ctrl+C, select a document and send it. Start `npm run receiver` again and click **Retry send**. A receiver restart clears its temporary receipts, so I only retry an uncertain accepted send while that receiver is still running.

When finished, I stop the receiver with Ctrl+C and run `docker compose down -v --remove-orphans`. That deletes the disposable patients and documents. I remove or disable the unpacked extension when I am not using the demo.

## How I put it together

I wrote the extension in TypeScript, which checks the shapes of messages before I build the browser files. It uses Manifest V3, Chrome's current extension format:

- `extension/content.ts` adds the selection panel to the native document screen. It reads document links for that patient, not document contents.
- `extension/background.ts` is a service worker, a background handler Chrome starts when a message arrives. It checks the sender and passes the selection to `extension/transfer.ts`.
- The transfer downloads only the selected files through the existing OpenEMR login, requests a receiver token valid for 30 seconds, and sends the batch. The token can be used once.
- `extension/options.ts` saves only the receiver address. Document contents and tokens never go into extension storage.
- `receiver/server.ts` checks tokens, file limits and duplicate requests. Its receipts last 10 minutes and are limited to 1,000 entries in memory.

I limit a send to 10 files, each at most 1 MiB, in PDF, plain text, PNG or JPEG format. Every transfer has a 20-second deadline. Redirects are refused. The extension requests access only to the loopback host `127.0.0.1`, the address for my own computer, plus permission to save settings. Its own checks restrict chart traffic to port 8080 and receiver traffic to ports 4318 and 4319. It has no permission to read other websites, browser history or cookies through Chrome's cookies API.

I pinned the demo to OpenEMR 7.0.3 and MariaDB 10.11 so the document layout is reproducible. I have not validated other OpenEMR versions. The receiver has no user authentication; a local process can request a token. The short-lived token demonstrates request expiry and replay protection, not production authorization. I would need a separate security and privacy review before considering any real health data. [Design and limits](docs/design.md) explains the boundaries.

## Tests and limits

There are 4 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



The relocated workflow did not complete successfully within the migration batch. Local test sources remain available.

No project-specific GitHub Actions workflow was retained. The local test sources remain in this folder.
