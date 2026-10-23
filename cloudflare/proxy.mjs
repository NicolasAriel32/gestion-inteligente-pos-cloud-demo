export function createHandler(fetchBackend = fetch) {
  return {
    async fetch(request, env) {
      const incoming = new URL(request.url);
      if (incoming.pathname !== '/api' && !incoming.pathname.startsWith('/api/')) {
        return env.ASSETS.fetch(request);
      }
      const error = (status, detail) => Response.json({ detail }, {
        status, headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' },
      });
      const origin = request.headers.get('Origin');
      const writing = !['GET', 'HEAD'].includes(request.method);
      if ((origin && origin !== incoming.origin) || (writing && origin !== incoming.origin)) {
        return error(403, 'Origen no permitido');
      }
      let backend;
      try {
        backend = new URL(env.BACKEND_URL);
        if (backend.protocol !== 'https:' || !backend.hostname.endsWith('.onrender.com') ||
            backend.username || backend.password || backend.port || backend.pathname !== '/' ||
            backend.search || backend.hash) throw new Error('Invalid backend');
      } catch {
        return error(503, 'La demo todavía no tiene conectado su servidor. Falta configurar BACKEND_URL en Cloudflare.');
      }
      const target = new URL(backend.origin);
      target.pathname = incoming.pathname;
      target.search = incoming.search;
      const headers = new Headers();
      for (const name of ['Accept', 'Content-Type', 'Cookie', 'X-CSRF-Token', 'Origin']) {
        const value = request.headers.get(name);
        if (value !== null) headers.set(name, value);
      }
      try {
        // Never retry a write. Existing idempotency/recovery belongs to the POS.
        const upstream = await fetchBackend(target, {
          method: request.method, headers,
          body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
          redirect: 'manual', signal: AbortSignal.timeout(90_000),
        });
        if (upstream.status >= 300 && upstream.status < 400) {
          return error(502, 'El servidor respondió con una redirección inesperada.');
        }
        if (upstream.headers.get('Content-Type')?.includes('text/html')) {
          return error(503, 'El servidor gratuito se está iniciando. Esperá aproximadamente un minuto y volvé a intentar.');
        }
        const responseHeaders = new Headers(upstream.headers);
        responseHeaders.set('Cache-Control', 'no-store');
        responseHeaders.set('X-Content-Type-Options', 'nosniff');
        return new Response(upstream.body, {
          status: upstream.status, statusText: upstream.statusText, headers: responseHeaders,
        });
      } catch {
        return error(502, 'El servidor no respondió. Si estabas confirmando una venta, recuperá el mismo intento antes de iniciar otra.');
      }
    },
  };
}
