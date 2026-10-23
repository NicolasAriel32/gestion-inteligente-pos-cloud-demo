import assert from 'node:assert/strict';
import test from 'node:test';
import { createHandler } from './proxy.mjs';

const origin = 'https://demo.example';
const env = { BACKEND_URL: 'https://pos-demo-api.onrender.com' };
const json = (body, status = 200, headers = {}) => Response.json(body, { status, headers });

test('forwards a write exactly once, preserving body, cookie and CSRF; returns secure cookie unchanged', async () => {
  let calls = 0;
  const payload = JSON.stringify({ idempotency_key: 'same-attempt' });
  const handler = createHandler(async (url, options) => {
    calls++;
    assert.equal(String(url), `${env.BACKEND_URL}/api/sales?test=1`);
    assert.equal(options.method, 'POST');
    assert.equal(options.redirect, 'manual');
    assert.equal(options.headers.get('Cookie'), 'pos_session=test-only');
    assert.equal(options.headers.get('X-CSRF-Token'), 'csrf-test');
    assert.equal(options.headers.get('Origin'), origin);
    assert.equal(options.headers.get('Authorization'), null);
    assert.equal(options.headers.get('X-Forwarded-Host'), null);
    assert.equal(await new Response(options.body).text(), payload);
    return json({ id: 1 }, 201, { 'Set-Cookie': 'pos_session=test-only; Secure; HttpOnly; SameSite=Strict; Path=/api' });
  });
  const response = await handler.fetch(new Request(`${origin}/api/sales?test=1`, {
    method: 'POST', body: payload,
    headers: { Origin: origin, 'Content-Type': 'application/json', Cookie: 'pos_session=test-only',
      'X-CSRF-Token': 'csrf-test', Authorization: 'not-forwarded', 'X-Forwarded-Host': 'evil.example' },
  }), env);
  assert.equal(calls, 1);
  assert.equal(response.status, 201);
  assert.match(response.headers.get('Set-Cookie'), /Secure; HttpOnly/);
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
  assert.deepEqual(await response.json(), { id: 1 });
});

test('GET health reaches the real backend; no health response is simulated', async () => {
  const handler = createHandler(async (url, options) => {
    assert.equal(String(url), `${env.BACKEND_URL}/api/health`);
    assert.equal(options.headers.get('Origin'), null);
    return json({ status: 'ok' });
  });
  assert.deepEqual(await (await handler.fetch(new Request(`${origin}/api/health`), env)).json(), { status: 'ok' });
});

test('cross-origin requests and originless writes are rejected before reaching the backend', async () => {
  const handler = createHandler(() => { throw new Error('must not be called'); });
  for (const [method, headers] of [['POST', {}], ['POST', { Origin: 'https://evil.example' }], ['GET', { Origin: 'null' }]]) {
    assert.equal((await handler.fetch(new Request(`${origin}/api/auth/login`, { method, headers }), env)).status, 403);
  }
});

test('missing and unsafe backend settings fail closed', async () => {
  const handler = createHandler(() => { throw new Error('must not be called'); });
  for (const BACKEND_URL of [undefined, 'http://localhost:8000', 'https://evil.example', 'https://user:pass@pos.onrender.com', 'https://pos.onrender.com/path', 'https://pos.onrender.com/?a=b']) {
    assert.equal((await handler.fetch(new Request(`${origin}/api/health`), { BACKEND_URL })).status, 503);
  }
});

test('an interrupted write is never retried automatically', async () => {
  let calls = 0;
  const handler = createHandler(async () => { calls++; throw new Error('connection interrupted'); });
  const response = await handler.fetch(new Request(`${origin}/api/sales`, { method: 'POST', headers: { Origin: origin } }), env);
  assert.equal(calls, 1);
  assert.equal(response.status, 502);
  assert.match((await response.json()).detail, /mismo intento/);
});

test('Render cold-start HTML is not passed to the JSON client', async () => {
  const handler = createHandler(async () => new Response('<html>Starting</html>', { headers: { 'Content-Type': 'text/html' } }));
  const response = await handler.fetch(new Request(`${origin}/api/health`), env);
  assert.equal(response.status, 503);
  assert.match(response.headers.get('Content-Type'), /application\/json/);
});

test('redirects are not followed and logout 204 remains empty', async () => {
  const request = new Request(`${origin}/api/auth/logout`, { method: 'POST', headers: { Origin: origin } });
  const redirect = createHandler(async () => new Response(null, { status: 302, headers: { Location: 'https://evil.example' } }));
  assert.equal((await redirect.fetch(request, env)).status, 502);
  const logout = createHandler(async () => new Response(null, { status: 204, headers: { 'Set-Cookie': 'pos_session=; Max-Age=0; Secure; HttpOnly; Path=/api' } }));
  const response = await logout.fetch(request, env);
  assert.equal(response.status, 204);
  assert.equal(await response.text(), '');
  assert.match(response.headers.get('Set-Cookie'), /Max-Age=0/);
});

test('frontend and SPA requests use compiled assets', async () => {
  const handler = createHandler(() => { throw new Error('must not fetch backend'); });
  for (const path of ['/', '/assets/index.js', '/catalogo']) {
    const request = new Request(`${origin}${path}`);
    const expected = new Response('compiled asset');
    assert.equal(await handler.fetch(request, { ASSETS: { fetch(received) { assert.equal(received, request); return expected; } } }), expected);
  }
});
