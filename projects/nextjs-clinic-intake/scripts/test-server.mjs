import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const directory = mkdtempSync(join(tmpdir(), "clinic-e2e-"));
const server = spawn(
  process.execPath,
  [
    "node_modules/next/dist/bin/next",
    "start",
    "--hostname",
    "127.0.0.1",
    "--port",
    "3187",
  ],
  {
    stdio: "inherit",
    env: {
      ...process.env,
      CLINIC_DB_PATH: join(directory, "queue.sqlite"),
      COOKIE_SECURE: "false",
    },
  },
);
const cleanup = () => rmSync(directory, { recursive: true, force: true });
server.once("spawn", () =>
  console.log(
    `Owned clinic test server: pid=${server.pid}; started=${new Date().toISOString()}; port=3187; cleanup=kill -TERM ${server.pid}`,
  ),
);
server.on("error", (error) => {
  console.error(error.message);
  cleanup();
  process.exit(1);
});
server.on("exit", (code) => {
  cleanup();
  process.exitCode = code ?? 0;
});
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => server.kill(signal));
