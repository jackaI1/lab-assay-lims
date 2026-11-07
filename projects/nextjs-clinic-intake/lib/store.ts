import Database from "better-sqlite3";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { randomUUID } from "node:crypto";
import { seedTickets, sortQueue, type Intake, type Ticket } from "./intake";

export class QueueError extends Error {}

// One connection per process. SQLite transactions serialize competing actions.
export function createStore(filename: string) {
  if (filename !== ":memory:")
    mkdirSync(dirname(filename), { recursive: true });
  const db = new Database(filename);
  db.pragma("journal_mode = WAL");
  db.pragma("busy_timeout = 5000");
  db.exec(`CREATE TABLE IF NOT EXISTS tickets (
    session TEXT NOT NULL, id TEXT NOT NULL, code TEXT NOT NULL,
    visit TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL, created INTEGER NOT NULL,
    requestId TEXT, PRIMARY KEY (session, id), UNIQUE(session, code), UNIQUE(session, requestId)
  ); CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY);`);
  const list = (session: string) =>
    db
      .prepare(
        "SELECT id, code, visit, priority, status, created FROM tickets WHERE session = ? ORDER BY created, code",
      )
      .all(session) as Ticket[];
  const insert = (session: string, ticket: Ticket) =>
    db
      .prepare(
        "INSERT INTO tickets (session, id, code, visit, priority, status, created) VALUES (?, ?, ?, ?, ?, ?, ?)",
      )
      .run(
        session,
        ticket.id,
        ticket.code,
        ticket.visit,
        ticket.priority,
        ticket.status,
        ticket.created,
      );
  const ensure = db.transaction((session: string) => {
    if (db.prepare("SELECT id FROM sessions WHERE id = ?").get(session)) return;
    db.prepare("INSERT INTO sessions VALUES (?)").run(session);
    seedTickets().forEach((ticket) => insert(session, ticket));
  });
  return {
    close: () => db.close(),
    list(session: string) {
      ensure(session);
      return list(session);
    },
    add: db.transaction(
      (session: string, intake: Intake, requestId = randomUUID()) => {
        ensure(session);
        const existing = db
          .prepare(
            "SELECT id, code, visit, priority, status, created FROM tickets WHERE session = ? AND requestId = ?",
          )
          .get(session, requestId) as Ticket | undefined;
        if (existing) return existing;
        const tickets = list(session);
        if (tickets.length >= 100)
          throw new QueueError(
            "This practice session has 100 tickets. Reset the demo to start again.",
          );
        const number =
          Math.max(0, ...tickets.map((t) => Number(t.code.slice(2)))) + 1;
        const ticket: Ticket = {
          ...intake,
          id: randomUUID(),
          code: `D-${String(number).padStart(3, "0")}`,
          status: "Waiting",
          created: Date.now(),
        };
        insert(session, ticket);
        db.prepare(
          "UPDATE tickets SET requestId = ? WHERE session = ? AND id = ?",
        ).run(requestId, session, ticket.id);
        return ticket;
      },
    ),
    reprioritize: db.transaction(
      (session: string, id: string, priority: Intake["priority"]) => {
        ensure(session);
        const result = db
          .prepare(
            "UPDATE tickets SET priority = ? WHERE session = ? AND id = ? AND status = 'Waiting'",
          )
          .run(priority, session, id);
        if (!result.changes)
          throw new QueueError(
            "That ticket is no longer waiting. Refresh the queue and try again.",
          );
      },
    ),
    callNext: db.transaction((session: string) => {
      ensure(session);
      const tickets = list(session);
      if (tickets.some((t) => t.status === "Called"))
        throw new QueueError(
          "Complete the called ticket before calling another.",
        );
      const next = sortQueue(tickets.filter((t) => t.status === "Waiting"))[0];
      if (!next)
        throw new QueueError("No tickets are waiting. Add an arrival first.");
      db.prepare(
        "UPDATE tickets SET status = 'Called' WHERE session = ? AND id = ?",
      ).run(session, next.id);
      return next;
    }),
    complete: db.transaction((session: string, id: string) => {
      ensure(session);
      const result = db
        .prepare(
          "UPDATE tickets SET status = 'Completed' WHERE session = ? AND id = ? AND status = 'Called'",
        )
        .run(session, id);
      if (!result.changes)
        throw new QueueError(
          "That ticket is no longer called. Refresh the queue and try again.",
        );
    }),
    reset: db.transaction((session: string) => {
      db.prepare("DELETE FROM tickets WHERE session = ?").run(session);
      db.prepare("DELETE FROM sessions WHERE id = ?").run(session);
      ensure(session);
    }),
  };
}
