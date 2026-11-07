export const runtime = "edge";
export async function GET() {
  // Liveness only: deliberately does not claim the Node database is healthy.
  return Response.json(
    {
      status: "ok",
      service: "clinic-intake-demo",
      runtime: "edge",
      check: "liveness",
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
