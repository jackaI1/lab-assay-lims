import { z } from "zod";

export const visits = [
  "Practice check-in",
  "Practice follow-up",
  "Practice screening",
] as const;
export const priorities = ["Soon", "Standard", "Flexible"] as const;
export const intakeSchema = z.object({
  visit: z.enum(visits),
  priority: z.enum(priorities),
});
export const prioritySchema = z.object({
  id: z.string().uuid(),
  priority: z.enum(priorities),
});
export type Intake = z.infer<typeof intakeSchema>;
export type Ticket = Intake & {
  id: string;
  code: string;
  status: "Waiting" | "Called" | "Completed";
  created: number;
};
export const SESSION_COOKIE = "clinic-demo-session";
export function sortQueue(tickets: Ticket[]) {
  return [...tickets].sort(
    (a, b) =>
      priorities.indexOf(a.priority) - priorities.indexOf(b.priority) ||
      a.created - b.created ||
      a.code.localeCompare(b.code),
  );
}
export function seedTickets(now = Date.now()): Ticket[] {
  return [
    {
      id: "10000000-0000-4000-8000-000000000001",
      code: "D-001",
      visit: visits[0],
      priority: "Standard",
      status: "Waiting",
      created: now - 12 * 60000,
    },
    {
      id: "10000000-0000-4000-8000-000000000002",
      code: "D-002",
      visit: visits[1],
      priority: "Soon",
      status: "Waiting",
      created: now - 7 * 60000,
    },
    {
      id: "10000000-0000-4000-8000-000000000003",
      code: "D-003",
      visit: visits[2],
      priority: "Flexible",
      status: "Waiting",
      created: now - 3 * 60000,
    },
  ];
}
