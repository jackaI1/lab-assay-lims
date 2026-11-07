import { randomUUID } from "node:crypto";
import { Activity, ArrowUpRight, Check, Clock3 } from "lucide-react";
import { readSession, getStore } from "@/lib/session";
import { seedTickets, sortQueue, priorities } from "@/lib/intake";
import { IntakeForm } from "@/components/intake-form";
import {
  PriorityControl,
  QueueForm,
  RefreshButton,
} from "@/components/queue-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ priority?: string }>;
}) {
  const session = await readSession();
  const tickets = session ? getStore().list(session) : seedTickets();
  const waiting = sortQueue(tickets.filter((t) => t.status === "Waiting"));
  const called = tickets.find((t) => t.status === "Called");
  const completed = tickets.filter((t) => t.status === "Completed");
  const { priority } = await searchParams;
  const filter = priorities.find((p) => p === priority);
  const visible = waiting.filter((t) => !filter || t.priority === filter);
  return (
    <>
      <header className="site-header">
        <div className="brand">
          <Activity aria-hidden="true" size={24} />
          <span>
            Clinic intake
            <span className="brand-sub">A practice workspace by Jack Lai</span>
          </span>
        </div>
        <Badge variant="outline">Fictional clinic</Badge>
      </header>
      <main id="main" className="workspace">
        <div className="intro">
          <div>
            <h1>A calmer way to manage arrivals.</h1>
            <p>
              Add a practice ticket, set its priority, and move it through the
              queue.
            </p>
          </div>
          <RefreshButton />
        </div>
        <aside className="demo-note" aria-label="Demo boundaries">
          <strong>Practice only.</strong> Anonymous tickets and fictional visit
          types. Do not use this for patient care or enter personal information.
          Each browser has its own queue.
        </aside>
        <div className="work-grid">
          <section className="intake-panel" aria-labelledby="arrival-title">
            <div className="section-title">
              <span className="section-icon">
                <ArrowUpRight aria-hidden="true" size={22} />
              </span>
              <h2 id="arrival-title">New arrival</h2>
            </div>
            <p>
              Ticket numbers are created for you. No names, notes, or medical
              details.
            </p>
            <IntakeForm requestId={randomUUID()} />
            <Separator />
            <div className="queue-rule">
              <h3>How the queue moves</h3>
              <p>
                Set priority yourself. Within each priority, the earliest
                arrival goes first. Only one ticket can be called at a time.
              </p>
            </div>
            <details className="reset-details">
              <summary>Start the demo again</summary>
              <p>
                This clears this browser’s tickets and restores the three sample
                arrivals.
              </p>
              <QueueForm command="reset">
                <label className="confirm-reset">
                  <input
                    type="checkbox"
                    name="confirm"
                    value="reset"
                    required
                  />{" "}
                  Clear my practice queue
                </label>
                <Button type="submit" variant="outline">
                  Reset demo
                </Button>
              </QueueForm>
            </details>
          </section>
          <section className="queue-panel" aria-labelledby="queue-title">
            <div className="queue-heading">
              <div>
                <h2 id="queue-title">Intake queue</h2>
                <p>Priority first. Arrival order second.</p>
              </div>
              <span className="waiting-count">{waiting.length} waiting</span>
            </div>
            <div className={`called-panel ${called ? "is-called" : ""}`}>
              <div className="called-label">
                <Clock3 size={18} aria-hidden="true" />
                {called ? "Now called" : "Ready for the next arrival"}
              </div>
              {called ? (
                <div className="called-content">
                  <div>
                    <strong>{called.code}</strong>
                    <p>{called.visit}</p>
                  </div>
                  <QueueForm command="complete" id={called.id}>
                    <Button type="submit">
                      <Check size={16} aria-hidden="true" />
                      Complete {called.code}
                    </Button>
                  </QueueForm>
                </div>
              ) : (
                <div className="called-content">
                  <p>
                    {waiting[0] ? (
                      <>
                        <strong>{waiting[0].code}</strong> is next in the full
                        queue.
                      </>
                    ) : (
                      "Add a practice arrival to begin."
                    )}
                  </p>
                  <QueueForm command="call">
                    <Button type="submit" disabled={!waiting.length}>
                      Call next ticket
                    </Button>
                  </QueueForm>
                </div>
              )}
            </div>
            <nav className="filter-nav" aria-label="Filter waiting tickets">
              {["All", ...priorities].map((p) => (
                <a
                  key={p}
                  href={p === "All" ? "/" : `/?priority=${p}`}
                  aria-current={
                    (!filter && p === "All") || filter === p
                      ? "page"
                      : undefined
                  }
                >
                  {p}
                </a>
              ))}
            </nav>
            <p className="filter-hint">
              Filtering changes the view. Call next always uses the full queue.
            </p>
            <ol className="ticket-list" aria-label="Waiting tickets">
              {visible.map((ticket) => (
                <li key={ticket.id} className="ticket">
                  <div className="ticket-info">
                    <div className="ticket-title">
                      <h3>{ticket.code}</h3>
                      <Badge
                        className={`priority-badge priority-${ticket.priority.toLowerCase()}`}
                      >
                        {ticket.priority}
                      </Badge>
                    </div>
                    <p>{ticket.visit}</p>
                    <span className="arrival-time">
                      Arrived{" "}
                      {new Date(ticket.created).toISOString().slice(11, 16)} UTC
                    </span>
                  </div>
                  <PriorityControl ticket={ticket} />
                </li>
              ))}
            </ol>
            {!visible.length && (
              <div className="empty-queue">
                <h3>
                  {filter
                    ? `No ${filter.toLowerCase()} tickets waiting`
                    : "The waiting queue is clear"}
                </h3>
                <p>
                  {filter
                    ? "Choose All to see the rest of the queue."
                    : "Add a practice arrival using the intake form."}
                </p>
              </div>
            )}
            <details className="completed-list">
              <summary>Completed tickets ({completed.length})</summary>
              {completed.length ? (
                <ul>
                  {completed
                    .slice(-5)
                    .reverse()
                    .map((t) => (
                      <li key={t.id}>
                        <Check size={16} aria-hidden="true" />
                        <strong>{t.code}</strong>
                        <span>{t.visit}</span>
                        <span>Completed</span>
                      </li>
                    ))}
                </ul>
              ) : (
                <p>Completed tickets will appear here.</p>
              )}
              {completed.length > 5 && (
                <p>Showing the latest five completions.</p>
              )}
            </details>
          </section>
        </div>
      </main>
      <footer>
        Built for practice, with synthetic data only.
        <a href="/api/intake-options">Demo intake options (JSON)</a>
      </footer>
    </>
  );
}
