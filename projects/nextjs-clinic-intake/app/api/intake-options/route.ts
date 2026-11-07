import { visits, priorities } from "@/lib/intake";
export const runtime = "edge";
export async function GET() {
  return Response.json(
    {
      demoOnly: true,
      version: 1,
      visits,
      priorities,
      ordering: "Staff priority, then earliest arrival",
      personalDataAllowed: false,
    },
    {
      headers: {
        "Cache-Control": "public, max-age=300",
        "X-Content-Type-Options": "nosniff",
      },
    },
  );
}
