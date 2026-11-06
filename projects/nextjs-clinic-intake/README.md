# nextjs-clinic-intake

I built a practice clinic intake queue to learn how the underlying idea works. This is a learning project.

## Run it locally

I use Node.js 24 and npm. No account, API key, or external database is needed.

```sh
npm ci
npm run dev
```

I stop the server with Ctrl+C. For a production build running locally over HTTP:

```sh
npm run build
COOKIE_SECURE=false npm start
```

`COOKIE_SECURE=false` is only for local HTTP. I leave it unset behind HTTPS. The app binds to 127.0.0.1 by default.

## Using the desk

- **Add practice arrival** assigns a ticket such as D-004. I choose from fixed fictional visit types.
- **Soon**, **Standard**, and **Flexible** are practice priorities I set myself. Earlier arrivals win ties.
- Each waiting ticket has a priority selector and **Save** button. Saving moves it to its new place.
- **Call next ticket** uses the whole queue, even if I have filtered the view. Only one ticket can be called at a time.
- **Complete** clears the called ticket and keeps it in the completed list. The screen shows the latest five completions.
- **Refresh queue** picks up changes from another tab in the same browser. There is no automatic live refresh.
- **Start the demo again** asks me to check a box before restoring the three samples. A session is limited to 100 tickets, including completions.

The queue survives a page reload and server restart. It is stored in `.data/clinic.sqlite`, a local database file, and a browser cookie identifies my practice session for 24 hours. Clearing the cookie starts a new practice queue. Old session records stay on disk until I delete the data folder with the server stopped.

## How I put it together

I use Next.js App Router, which organizes pages and server endpoints by folder. The page in `app/page.tsx` is a server component: it reads the queue and builds the page on the server. Small interactive components handle forms, pending states, and feedback.

The buttons, labels, badges, and dividers come from shadcn/ui. Its component source is checked into `components/ui/`, so I can adjust it. I use native dropdowns for visit and priority choices, with visible labels, keyboard focus, and inline errors. The layout stacks on a phone and places intake beside the queue on a wider screen.

Forms call server actions in `app/actions.ts`, functions that run on the server. Zod checks each submitted value against the allowed choices before storage changes. SQLite transactions keep checking and updating a ticket together, so repeated calls cannot put two tickets in the called state. Stale changes return a useful message. A submission ID prevents a retried arrival from creating a duplicate ticket. The page reloads its server-rendered queue after each successful change.

Two read-only edge route handlers run without the Node database: `/api/intake-options` returns the allowed demo choices for a practice kiosk or another client, and `/api/health` reports that the app can answer a request. An edge handler uses web APIs instead of Node-only APIs. Health is a liveness check, not a database check. The current Next.js release warns that its edge runtime is deprecated; I kept these two small routes to make that boundary explicit.

I describe the storage boundary, session isolation, and endpoints in [the design notes](docs/design.md).

## Tests and limits

There are 3 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Retained project workflows: `nextjs-clinic-intake-ci.yml`. Their commands use this folder and their triggers use its paths.
