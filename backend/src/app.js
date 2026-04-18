const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const axios = require('axios');

const app = express();
const PORT = process.env.PORT || 8080;

// ─────────────────────────────────────────────
// MIDDLEWARE
// ─────────────────────────────────────────────
app.use(helmet({ contentSecurityPolicy: false }));
app.use(compression());
app.use(cors({
  origin: process.env.FRONTEND_URL || '*',
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Request logger
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const ms = Date.now() - start;
    console.log(`${req.method} ${req.path} ${res.statusCode} ${ms}ms`);
  });
  next();
});

// ─────────────────────────────────────────────
// API Gateway Axios client dengan retry
// ─────────────────────────────────────────────
const API_GATEWAY_URL = process.env.API_GATEWAY_URL;

const apiClient = axios.create({
  baseURL: API_GATEWAY_URL,
  timeout: 25000,
  headers: { 'Content-Type': 'application/json' }
});

// Retry interceptor (3x retry untuk network error)
apiClient.interceptors.response.use(
  response => response,
  async error => {
    const config = error.config;
    config._retryCount = (config._retryCount || 0) + 1;
    if (config._retryCount <= 3 && (!error.response || error.response.status >= 500)) {
      await new Promise(resolve => setTimeout(resolve, 1000 * config._retryCount));
      return apiClient(config);
    }
    return Promise.reject(error);
  }
);

// ─────────────────────────────────────────────
// ROUTES
// ─────────────────────────────────────────────

// Health check — digunakan oleh Beanstalk health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    environment: process.env.NODE_ENV || 'development'
  });
});

// Info endpoint
app.get('/', (req, res) => {
  res.json({
    name: 'myapp-backend',
    version: '1.0.0',
    endpoints: ['GET /health', 'GET /data', 'POST /data']
  });
});

// ── POST /data → Forward ke Lambda via API Gateway ────────────────
app.post('/data', async (req, res) => {
  try {
    if (!API_GATEWAY_URL) {
      return res.status(503).json({ error: 'API Gateway URL not configured' });
    }

    const response = await apiClient.post('/data', req.body);
    return res.status(response.status).json(response.data);
  } catch (err) {
    if (err.response) {
      return res.status(err.response.status).json(err.response.data);
    }
    console.error('POST /api/data error:', err.message);
    return res.status(500).json({ error: 'Failed to reach API Gateway', detail: err.message });
  }
});

// ── GET /data → Forward ke Lambda via API Gateway ─────────────────
app.get('/data', async (req, res) => {
  try {
    if (!API_GATEWAY_URL) {
      return res.status(503).json({ error: 'API Gateway URL not configured' });
    }

    const response = await apiClient.get('/data', { params: req.query });
    return res.json(response.data);
  } catch (err) {
    if (err.response) {
      return res.status(err.response.status).json(err.response.data);
    }
    console.error('GET /api/data error:', err.message);
    return res.status(500).json({ error: 'Failed to reach API Gateway', detail: err.message });
  }
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: `Route ${req.method} ${req.path} not found` });
});

// Error handler
app.use((err, req, res, next) => {
  console.error('Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// ─────────────────────────────────────────────
// START SERVER
// ─────────────────────────────────────────────
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`✅ Backend server running on port ${PORT}`);
    console.log(`   API Gateway URL: ${API_GATEWAY_URL || '(not set)'}`);
    console.log(`   Environment: ${process.env.NODE_ENV || 'development'}`);
  });
}

module.exports = app;
