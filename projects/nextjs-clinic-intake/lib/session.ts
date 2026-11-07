import "server-only";
import { cookies } from "next/headers";
import { randomUUID } from "node:crypto";
import { z } from "zod";
import { createStore } from "./store";
import { SESSION_COOKIE } from "./intake";

const globalStore = globalThis as unknown as {
  clinicStore?: ReturnType<typeof createStore>;
};
export function getStore() {
  return (globalStore.clinicStore ??= createStore(
    process.env.CLINIC_DB_PATH || ".data/clinic.sqlite",
  ));
}
export async function readSession() {
  const value = (await cookies()).get(SESSION_COOKIE)?.value;
  return z.string().uuid().safeParse(value).success ? value : undefined;
}
export async function actionSession() {
  const existing = await readSession();
  if (existing) return existing;
  const id = randomUUID();
  (await cookies()).set(SESSION_COOKIE, id, {
    httpOnly: true,
    sameSite: "lax",
    secure:
      process.env.NODE_ENV === "production" &&
      process.env.COOKIE_SECURE !== "false",
    path: "/",
    maxAge: 60 * 60 * 24,
  });
  return id;
}
