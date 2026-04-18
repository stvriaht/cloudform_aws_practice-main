const request = require('supertest');
const app = require('../src/app');

describe('Backend API Tests', () => {

  // ── Health Check ────────────────────────────────────────────────────
  describe('GET /health', () => {
    test('returns 200 with status healthy', async () => {
      const res = await request(app).get('/health');
      expect(res.statusCode).toBe(200);
      expect(res.body.status).toBe('healthy');
      expect(res.body).toHaveProperty('timestamp');
      expect(res.body).toHaveProperty('uptime');
    });
  });

  // ── Root Endpoint ───────────────────────────────────────────────────
  describe('GET /', () => {
    test('returns API info', async () => {
      const res = await request(app).get('/');
      expect(res.statusCode).toBe(200);
      expect(res.body).toHaveProperty('name', 'myapp-backend');
      expect(res.body).toHaveProperty('endpoints');
    });
  });

  // ── 404 ─────────────────────────────────────────────────────────────
  describe('404 Handler', () => {
    test('returns 404 for unknown routes', async () => {
      const res = await request(app).get('/unknown-route');
      expect(res.statusCode).toBe(404);
    });
  });

  // ── POST /api/data ───────────────────────────────────────────────────
  describe('POST /api/data', () => {
    test('returns 503 when API_GATEWAY_URL not set', async () => {
      const originalUrl = process.env.API_GATEWAY_URL;
      delete process.env.API_GATEWAY_URL;

      const res = await request(app)
        .post('/api/data')
        .send({ name: 'test', value: 10 });

      expect(res.statusCode).toBe(503);
      process.env.API_GATEWAY_URL = originalUrl;
    });
  });

  // ── GET /api/data ────────────────────────────────────────────────────
  describe('GET /api/data', () => {
    test('returns 503 when API_GATEWAY_URL not set', async () => {
      const originalUrl = process.env.API_GATEWAY_URL;
      delete process.env.API_GATEWAY_URL;

      const res = await request(app).get('/api/data');
      expect(res.statusCode).toBe(503);

      process.env.API_GATEWAY_URL = originalUrl;
    });
  });

  // ── CORS Headers ─────────────────────────────────────────────────────
  describe('CORS', () => {
    test('health endpoint has CORS headers', async () => {
      const res = await request(app)
        .get('/health')
        .set('Origin', 'https://example.com');

      expect(res.headers['access-control-allow-origin']).toBeDefined();
    });
  });

});
