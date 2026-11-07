import { afterEach, describe, expect, it } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createStore } from "@/lib/store";
import { intakeSchema, seedTickets, sortQueue } from "@/lib/intake";

const stores: ReturnType<typeof createStore>[] = [];
function store() {
  const value = createStore(":memory:");
  stores.push(value);
  return value;
}
afterEach(() => {
  stores.splice(0).forEach((s) => s.close());
});
describe("intake validation", () => {
  it("accepts only the fixed practice visit and priority choices", () => {
    expect(
      intakeSchema.safeParse({ visit: "Practice check-in", priority: "Soon" })
        .success,
    ).toBe(true);
    expect(
      intakeSchema.safeParse({ visit: "a real medical note", priority: "Soon" })
        .success,
    ).toBe(false);
    expect(
      intakeSchema.safeParse({
        visit: "Practice check-in",
        priority: "Emergency",
      }).success,
    ).toBe(false);
    expect(intakeSchema.safeParse({}).success).toBe(false);
  });
  it("drops arbitrary extra fields rather than storing personal details", () => {
    expect(
      intakeSchema.parse({
        visit: "Practice check-in",
        priority: "Standard",
        note: "discard this",
      }),
    ).not.toHaveProperty("note");
  });
});
describe("queue persistence and transitions", () => {
  it("seeds once for each isolated session", () => {
    const s = store();
    expect(s.list("a")).toHaveLength(3);
    s.add("a", { visit: "Practice check-in", priority: "Soon" });
    expect(s.list("a")).toHaveLength(4);
    expect(s.list("b")).toHaveLength(3);
  });
  it("generates unique anonymous ticket codes", () => {
    const s = store();
    expect(
      s.add("a", { visit: "Practice check-in", priority: "Standard" }).code,
    ).toBe("D-004");
    expect(
      s.add("a", { visit: "Practice follow-up", priority: "Standard" }).code,
    ).toBe("D-005");
  });
  it("orders by priority then arrival without mutating the original list", () => {
    const original = seedTickets(1000000);
    expect(sortQueue(original).map((t) => t.code)).toEqual([
      "D-002",
      "D-001",
      "D-003",
    ]);
    expect(original[0].code).toBe("D-001");
  });
  it("uses earlier arrival within an equal priority", () => {
    const s = store();
    s.reprioritize("a", s.list("a")[1].id, "Standard");
    expect(s.callNext("a").code).toBe("D-001");
  });
  it("moves the earliest highest priority ticket through called to completed", () => {
    const s = store();
    const ticket = s.callNext("a");
    expect(ticket.code).toBe("D-002");
    expect(s.list("a").find((t) => t.id === ticket.id)?.status).toBe("Called");
    s.complete("a", ticket.id);
    expect(s.list("a").find((t) => t.id === ticket.id)?.status).toBe(
      "Completed",
    );
    expect(s.callNext("a").code).toBe("D-001");
  });
  it("prevents repeated call requests from calling a second ticket", () => {
    const s = store();
    s.callNext("a");
    expect(() => s.callNext("a")).toThrow("Complete the called ticket");
    expect(s.list("a").filter((t) => t.status === "Called")).toHaveLength(1);
  });
  it("rejects completion of waiting tickets and stale completions", () => {
    const s = store();
    expect(() => s.complete("a", s.list("a")[0].id)).toThrow(
      "no longer called",
    );
    const called = s.callNext("a");
    s.complete("a", called.id);
    expect(() => s.complete("a", called.id)).toThrow("no longer called");
  });
  it("rejects changing called tickets and missing IDs", () => {
    const s = store();
    const called = s.callNext("a");
    expect(() => s.reprioritize("a", called.id, "Flexible")).toThrow(
      "no longer waiting",
    );
    expect(() => s.reprioritize("a", "missing", "Soon")).toThrow(
      "no longer waiting",
    );
  });
  it("does not allow another session to complete or change a new ticket", () => {
    const s = store();
    const added = s.add("a", { visit: "Practice check-in", priority: "Soon" });
    expect(() => s.reprioritize("b", added.id, "Flexible")).toThrow();
    expect(() => s.complete("b", added.id)).toThrow();
    expect(s.list("a").find((t) => t.id === added.id)?.priority).toBe("Soon");
  });
  it("gives a useful error when the waiting queue is empty", () => {
    const s = store();
    for (let i = 0; i < 3; i++) s.complete("a", s.callNext("a").id);
    expect(() => s.callNext("a")).toThrow("No tickets are waiting");
  });
  it("resets only the current session", () => {
    const s = store();
    s.add("a", { visit: "Practice check-in", priority: "Standard" });
    s.add("b", { visit: "Practice check-in", priority: "Standard" });
    s.reset("a");
    expect(s.list("a")).toHaveLength(3);
    expect(s.list("b")).toHaveLength(4);
  });
  it("bounds a session to 100 tickets including completed tickets", () => {
    const s = store();
    for (let i = 0; i < 97; i++)
      s.add("a", { visit: "Practice check-in", priority: "Standard" });
    expect(() =>
      s.add("a", { visit: "Practice check-in", priority: "Standard" }),
    ).toThrow("100 tickets");
    expect(s.list("a")).toHaveLength(100);
  });
  it("survives closing and reopening the database", () => {
    const directory = mkdtempSync(join(tmpdir(), "clinic-unit-"));
    try {
      const path = join(directory, "queue.sqlite");
      const first = createStore(path);
      try {
        first.add("persistent", {
          visit: "Practice screening",
          priority: "Standard",
        });
      } finally {
        first.close();
      }
      const second = createStore(path);
      try {
        expect(second.list("persistent")).toHaveLength(4);
      } finally {
        second.close();
      }
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
});

it("deduplicates a retried arrival without reopening a completed ticket", () => {
  const s = store();
  const intake = { visit: "Practice screening", priority: "Soon" } as const;
  const ticket = s.add("a", intake, "submission-id");
  expect(s.add("a", intake, "submission-id").id).toBe(ticket.id);
  expect(s.list("a")).toHaveLength(4);
  s.complete("a", s.callNext("a").id);
  s.complete("a", s.callNext("a").id);
  expect(s.add("a", intake, "submission-id").status).toBe("Completed");
  expect(s.list("a")).toHaveLength(4);
});
