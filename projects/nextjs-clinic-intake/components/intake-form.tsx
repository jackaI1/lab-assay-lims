"use client";
import { useActionState, useEffect, useRef } from "react";
import { addArrival } from "@/app/actions";
import { visits, priorities } from "@/lib/intake";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export function IntakeForm({ requestId }: { requestId: string }) {
  const [state, action, pending] = useActionState(addArrival, { message: "" });
  const formRef = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (state.errors)
      formRef.current
        ?.querySelector<HTMLElement>('[aria-invalid="true"]')
        ?.focus();
  }, [state]);
  return (
    <form ref={formRef} action={action} noValidate className="intake-form">
      <input type="hidden" name="requestId" value={requestId} />
      <div className="field">
        <Label htmlFor="visit">Practice visit type</Label>
        <select
          id="visit"
          name="visit"
          required
          defaultValue=""
          aria-invalid={!!state.errors?.visit}
          aria-describedby={state.errors?.visit ? "visit-error" : undefined}
        >
          <option value="" disabled>
            Choose a visit type
          </option>
          {visits.map((visit) => (
            <option key={visit}>{visit}</option>
          ))}
        </select>
        {state.errors?.visit && (
          <p id="visit-error" className="field-error">
            Choose one of the practice visit types.
          </p>
        )}
      </div>
      <div className="field">
        <Label htmlFor="priority">Staff-selected priority</Label>
        <select
          id="priority"
          name="priority"
          defaultValue="Standard"
          required
          aria-invalid={!!state.errors?.priority}
          aria-describedby="priority-help"
        >
          {priorities.map((priority) => (
            <option key={priority}>{priority}</option>
          ))}
        </select>
        <p id="priority-help" className="hint">
          Soon goes first, then Standard, then Flexible. This demo does not
          assess medical urgency.
        </p>
      </div>
      <Button type="submit" size="lg" disabled={pending} className="w-full">
        {pending ? "Adding arrival…" : "Add practice arrival"}
      </Button>
      <p
        role="status"
        className={state.ok === false ? "field-error feedback" : "feedback"}
      >
        {state.message}
      </p>
    </form>
  );
}
