import { createReceiver } from "./server.js";
const port = Number(process.env.PORT ?? 4318);
if (![4318, 4319].includes(port)) throw new Error("Use port 4318 or 4319.");
const { server } = createReceiver();
server.listen(port, "127.0.0.1", () =>
  console.log(`Fictional-document receiver: http://127.0.0.1:${port}`),
);
for (const signal of ["SIGINT", "SIGTERM"] as const)
  process.on(signal, () => server.close(() => process.exit(0)));
