"use client";
import { Button } from "@/components/ui/button";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="workspace">
      <h1>The practice queue could not load.</h1>
      <p>
        Try loading it again. If this continues, check that the local data
        folder is writable.
      </p>
      <Button onClick={reset}>Try again</Button>
    </main>
  );
}
