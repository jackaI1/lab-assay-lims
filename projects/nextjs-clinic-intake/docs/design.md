# Queue design

I keep the practice desk small enough to run on one computer while making state changes real.

## Request path

1. `app/page.tsx` reads an HttpOnly session cookie. Without one it displays three synthetic tickets without writing a cookie during server rendering.
2. The first valid server action creates a random UUID cookie and seeds that session in SQLite. Later actions obtain the session from the cookie, never a submitted session field.
3. `app/actions.ts` validates every mutation, including IDs, command names, enum choices, and reset confirmation. Unknown extra intake fields are discarded. Each rendered intake form carries a random submission ID. A unique database constraint makes a retry return the original ticket, so refreshing a JavaScript-free form submission does not duplicate it. A fresh form render creates a new ID for the next arrival.
4. `lib/store.ts` uses bound SQL parameters and synchronous transactions. All queries include the session. The server-only session module owns the singleton connection. Page reads and action writes share the database.
5. A successful action calls `revalidatePath('/')`, which refreshes the server component output. The browser announces feedback through a status region. Intake validation also focuses the first invalid dropdown.

The session UUID acts as a bearer credential for anonymous synthetic data, not an authenticated identity. A copied cookie shares a queue. Cookies are HttpOnly, SameSite=Lax, expire after 24 hours, and are Secure in production unless explicitly overridden for local HTTP. Next.js also performs its own same-origin server-action checks. The app does not accept names, contact information, dates of birth, free text, or medical notes.

## State and ordering

A ticket moves from Waiting to Called to Completed. Priority can change only while Waiting. Only one ticket may be Called per session. Call-next checks that rule and chooses a ticket within the same transaction. Repeated completion and stale priority writes fail rather than silently changing another ticket. Priority order is Soon, Standard, Flexible, then timestamp and ticket code for deterministic ties. Filtering affects display only.

SQLite is a disk-backed database, not a global in-memory array. WAL mode and a five-second busy timeout support concurrent local connections; transactions serialize writes. It needs a writable persistent disk and a Node host with the better-sqlite3 native module. It is not suitable for a deployment with many independent ephemeral serverless disks. I would use a shared database before scaling across hosts.

`CLINIC_DB_PATH` can move the database, for example `CLINIC_DB_PATH=/tmp/clinic-demo.sqlite npm run dev`. Each session allows 100 total tickets. There is no global session quota or background expiry worker. To remove all stored demo sessions, stop the app and delete `.data/`. No records are committed to Git.

## Edge endpoints

Both handlers explicitly export `runtime = 'edge'` and use web-standard `Response.json`:

```sh
curl http://127.0.0.1:3000/api/intake-options
curl http://127.0.0.1:3000/api/health
```

The intake-options response includes `demoOnly`, a version, fixed visit types, priorities, ordering text, and `personalDataAllowed: false`. It can be cached for five minutes. Health returns liveness only with no-store. Neither endpoint reads cookies, tickets, the filesystem, or SQLite. The shared enum module is edge-compatible. Next.js 16.4 marks the edge runtime deprecated; a future upgrade can move these endpoints to Node without changing their response contracts.

## Verification and resource ownership

Unit tests open in-memory databases and close each after the test. The persistence test uses a temporary directory and deletes it in finally. Browser tests use a production build at 127.0.0.1:3187. Playwright owns the server wrapper; the wrapper records the exact server PID, start time, port, and stop command, forwards termination signals, and removes its temporary SQLite directory on child exit. Tests use one worker to limit resource use. Playwright closes its fixture pages; explicitly created browser contexts close in finally blocks. Existing servers are never reused or stopped.

CI uses Node 24 and the committed npm lockfile. It installs Chromium, runs the desktop and mobile projects, and uploads failure traces for three days only if a check fails. It runs on both pull requests and main. There were no tests or app features in the initial repository.

The accessibility checks cover automated WCAG A/AA rules, including contrast, as well as form labels, keyboard focus after validation, the skip link, and mobile overflow. They do not replace a screen-reader review with real users.
