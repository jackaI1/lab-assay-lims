"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";
import { actionSession, getStore } from "@/lib/session";
import { intakeSchema, prioritySchema } from "@/lib/intake";
import { QueueError } from "@/lib/store";

export type ActionState = {
  message: string;
  errors?: Record<string, string[] | undefined>;
  ok?: boolean;
};
const commandSchema = z.discriminatedUnion("command", [
  z.object({ command: z.literal("call") }),
  z.object({ command: z.literal("complete"), id: z.string().uuid() }),
  z.object({ command: z.literal("priority"), ...prioritySchema.shape }),
  z.object({ command: z.literal("reset"), confirm: z.literal("reset") }),
]);
function failure(error: unknown): ActionState {
  // Do not leak database paths or internals into the UI.
  return {
    message:
      error instanceof QueueError
        ? error.message
        : "The queue could not be saved. Try again or refresh the page.",
    ok: false,
  };
}
export async function addArrival(
  _: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const result = intakeSchema
    .extend({ requestId: z.string().uuid() })
    .safeParse(Object.fromEntries(formData));
  if (!result.success)
    return {
      message: "Choose a visit type and a priority.",
      errors: result.error.flatten().fieldErrors,
      ok: false,
    };
  try {
    const ticket = getStore().add(
      await actionSession(),
      { visit: result.data.visit, priority: result.data.priority },
      result.data.requestId,
    );
    revalidatePath("/");
    return { message: `${ticket.code} added to the waiting queue.`, ok: true };
  } catch (error) {
    return failure(error);
  }
}
export async function updateQueue(
  _: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const result = commandSchema.safeParse(Object.fromEntries(formData));
  if (!result.success)
    return {
      message: "The queue request is invalid. Refresh the page and try again.",
      ok: false,
    };
  try {
    const session = await actionSession();
    const store = getStore();
    const data = result.data;
    let message = "";
    switch (data.command) {
      case "call":
        message = `${store.callNext(session).code} called. Complete this ticket when finished.`;
        break;
      case "complete":
        store.complete(session, data.id);
        message = "Ticket completed.";
        break;
      case "priority":
        store.reprioritize(session, data.id, data.priority);
        message = "Priority saved. Waiting order updated.";
        break;
      case "reset":
        store.reset(session);
        message = "Demo reset to three fictional tickets.";
        break;
    }
    revalidatePath("/");
    return { message, ok: true };
  } catch (error) {
    return failure(error);
  }
}
