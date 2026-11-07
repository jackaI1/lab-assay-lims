"use client";
import { useActionState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { updateQueue } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { priorities, type Ticket } from "@/lib/intake";

export function QueueForm({
  command,
  id,
  children,
  className = "",
}: {
  command: "call" | "complete" | "priority" | "reset";
  id?: string;
  children: ReactNode;
  className?: string;
}) {
  const [state, action, pending] = useActionState(updateQueue, { message: "" });
  return (
    <form action={action} className={`queue-form ${className}`}>
      <input type="hidden" name="command" value={command} />
      {id && <input type="hidden" name="id" value={id} />}
      <fieldset disabled={pending}>{children}</fieldset>
      <p
        role="status"
        className={state.ok === false ? "field-error feedback" : "feedback"}
      >
        {pending ? "Saving…" : state.message}
      </p>
    </form>
  );
}
export function PriorityControl({ ticket }: { ticket: Ticket }) {
  return (
    <QueueForm command="priority" id={ticket.id} className="priority-form">
      <label className="sr-only" htmlFor={`priority-${ticket.id}`}>
        Priority for {ticket.code}
      </label>
      <select
        id={`priority-${ticket.id}`}
        name="priority"
        defaultValue={ticket.priority}
      >
        {priorities.map((p) => (
          <option key={p}>{p}</option>
        ))}
      </select>
      <Button
        variant="outline"
        type="submit"
        size="sm"
        aria-label={`Save priority for ${ticket.code}`}
      >
        Save
      </Button>
    </QueueForm>
  );
}
export function RefreshButton() {
  const router = useRouter();
  return (
    <Button variant="outline" onClick={() => router.refresh()}>
      Refresh queue
    </Button>
  );
}
