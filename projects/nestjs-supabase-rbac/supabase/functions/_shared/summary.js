/** Forward the caller's identity; this function never receives an elevated database key. */
export function summaryHandler(apiBaseUrl, fetchApi = fetch) {
  return async (request) => {
    const json = (body, status) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store' } });
    if (request.method !== 'GET') return json({ error: 'Use GET' }, 405);
    const token = request.headers.get('authorization');
    if (!token || !/^Bearer [^\s]+$/.test(token)) return json({ error: 'Access token required' }, 401);
    const clinic = new URL(request.url).searchParams.get('clinicId');
    if (!clinic || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(clinic)) return json({ error: 'A clinicId UUID is required' }, 400);
    if (!apiBaseUrl) return json({ error: 'API is not configured' }, 503);
    try {
      const response = await fetchApi(`${apiBaseUrl.replace(/\/$/, '')}/clinics/${clinic}/appointments`, {
        headers: { Authorization: token }, signal: AbortSignal.timeout(5000), redirect: 'error',
      });
      if (!response.ok) return json({ error: 'API denied or could not complete the request' }, [401,403,404].includes(response.status) ? response.status : 502);
      const appointments = await response.json();
      return json({ clinicId: clinic, appointments }, 200);
    } catch { return json({ error: 'API unavailable' }, 502); }
  };
}
