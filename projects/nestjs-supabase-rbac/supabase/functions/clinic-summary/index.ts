import { summaryHandler } from '../_shared/summary.js';
Deno.serve(summaryHandler(Deno.env.get('API_BASE_URL')));
