import { createApp } from './app';
async function main() {
  if (!process.env.SUPABASE_URL || !process.env.SUPABASE_ANON_KEY) throw new Error('Set SUPABASE_URL and SUPABASE_ANON_KEY');
  const app = await createApp();
  app.enableShutdownHooks();
  await app.listen(Number(process.env.PORT ?? 3000), '0.0.0.0');
}
main().catch(() => { console.error('API startup failed. Check configuration and port availability.'); process.exitCode = 1; });
