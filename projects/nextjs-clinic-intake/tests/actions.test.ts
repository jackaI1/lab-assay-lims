import { beforeEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({
  add: vi.fn(),
  reprioritize: vi.fn(),
  callNext: vi.fn(),
  complete: vi.fn(),
  reset: vi.fn(),
  session: vi.fn(),
  revalidate: vi.fn(),
}));
vi.mock("@/lib/session", () => ({
  getStore: () => mocks,
  actionSession: mocks.session,
}));
vi.mock("next/cache", () => ({ revalidatePath: mocks.revalidate }));
import { addArrival, updateQueue } from "@/app/actions";
import { QueueError } from "@/lib/store";
const form = (data: Record<string, string>) => {
  const f = new FormData();
  Object.entries(data).forEach(([k, v]) => f.set(k, v));
  if (!f.has("requestId"))
    f.set("requestId", "20000000-0000-4000-8000-000000000001");
  return f;
};
beforeEach(() => {
  vi.resetAllMocks();
  mocks.session.mockResolvedValue("session-a");
});
it("returns field errors before a malformed arrival reaches storage", async () => {
  const result = await addArrival(
    { message: "" },
    form({ visit: "bad", priority: "Soon" }),
  );
  expect(result.errors?.visit).toBeDefined();
  expect(mocks.add).not.toHaveBeenCalled();
});
it("stores valid arrivals under the server cookie session and revalidates the page", async () => {
  mocks.add.mockReturnValue({ code: "D-004" });
  const result = await addArrival(
    { message: "" },
    form({ visit: "Practice check-in", priority: "Soon", session: "forged" }),
  );
  expect(mocks.add).toHaveBeenCalledWith(
    "session-a",
    { visit: "Practice check-in", priority: "Soon" },
    "20000000-0000-4000-8000-000000000001",
  );
  expect(mocks.revalidate).toHaveBeenCalledWith("/");
  expect(result.ok).toBe(true);
});
it("validates command, IDs and reset confirmation on the server", async () => {
  for (const data of [
    { command: "bad" },
    { command: "complete", id: "bad" },
    { command: "priority", id: "bad", priority: "Soon" },
    { command: "reset" },
  ] as Record<string, string>[]) {
    expect((await updateQueue({ message: "" }, form(data))).ok).toBe(false);
  }
  expect(mocks.session).not.toHaveBeenCalled();
});
it("returns actionable transition conflicts", async () => {
  mocks.callNext.mockImplementation(() => {
    throw new QueueError("Complete the called ticket before calling another.");
  });
  expect(
    (await updateQueue({ message: "" }, form({ command: "call" }))).message,
  ).toContain("Complete the called ticket");
});
it("does not expose unexpected storage errors", async () => {
  mocks.add.mockImplementation(() => {
    throw new Error("private database location");
  });
  const result = await addArrival(
    { message: "" },
    form({ visit: "Practice check-in", priority: "Soon" }),
  );
  expect(result.message).toContain("could not be saved");
  expect(result.message).not.toContain("private");
});

it("rejects an invalid submission ID before storing an arrival", async () => {
  const result = await addArrival(
    { message: "" },
    form({
      visit: "Practice check-in",
      priority: "Soon",
      requestId: "invalid",
    }),
  );
  expect(result.ok).toBe(false);
  expect(mocks.add).not.toHaveBeenCalled();
});
