import { useState, useEffect, useCallback } from 'react';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale,
  PointElement, LineElement, BarElement,
  Title, Tooltip, Legend, Filler
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale, LinearScale, PointElement,
  LineElement, BarElement, Title, Tooltip, Legend, Filler
);

// ─── Config ───────────────────────────────────────────────────────────────
const API_URL = import.meta.env.VITE_API_URL || '/api';

const CHART_COLORS = {
  primary:   'rgba(129, 140, 248, 0.9)',
  secondary: 'rgba(167, 139, 250, 0.9)',
  tertiary:  'rgba(52, 211, 153, 0.9)',
  fill:      'rgba(79, 70, 229, 0.15)',
};

const CHART_OPTIONS_BASE = {
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend: {
      labels: { color: '#9ca3af', font: { family: 'Inter', size: 12 } }
    },
    tooltip: {
      backgroundColor: '#1a1a2e',
      titleColor: '#818cf8',
      bodyColor: '#e2e8f0',
      borderColor: 'rgba(79,70,229,0.4)',
      borderWidth: 1,
    }
  },
  scales: {
    x: {
      ticks: { color: '#6b7280', font: { size: 11 } },
      grid:  { color: 'rgba(255,255,255,0.05)' },
    },
    y: {
      ticks: { color: '#6b7280', font: { size: 11 } },
      grid:  { color: 'rgba(255,255,255,0.05)' },
    }
  }
};

// ─── Komponen StatCard ─────────────────────────────────────────────────────
function StatCard({ label, value, sub }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

// ─── App utama ─────────────────────────────────────────────────────────────
export default function App() {
  const [data, setData]       = useState([]);
  const [stats, setStats]     = useState([]);
  const [timeseries, setTS]   = useState([]);
  const [pagination, setPag]  = useState({ total: 0, limit: 50, offset: 0 });
  const [loading, setLoading] = useState(false);
  const [submitting, setSub]  = useState(false);
  const [message, setMessage] = useState(null); // { type: 'success'|'error', text }

  const [form, setForm] = useState({
    name: '', value: '', category: 'sensor'
  });

  // ── Fetch data ─────────────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/data?limit=50`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json.data || []);
      setStats(json.statistics || []);
      setTS(json.timeseries || []);
      setPag(json.pagination || { total: 0, limit: 50, offset: 0 });
    } catch (e) {
      setMessage({ type: 'error', text: `Gagal mengambil data: ${e.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    // Auto-refresh setiap 30 detik
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // ── Submit form ────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSub(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_URL}/data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          value: parseFloat(form.value),
          category: form.category
        })
      });
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json.errors?.join(', ') || json.error || `HTTP ${res.status}`);
      }
      setMessage({ type: 'success', text: `✅ Data "${form.name}" berhasil disimpan (ID: ${json.data?.id})` });
      setForm({ name: '', value: '', category: 'sensor' });
      fetchData();
    } catch (e) {
      setMessage({ type: 'error', text: `❌ ${e.message}` });
    } finally {
      setSub(false);
    }
  };

  // ── Chart data — Line (time series atau data terbaru) ─────────────
  const lineData = {
    labels: data.slice(0, 20).reverse().map(d =>
      d.name.length > 12 ? d.name.slice(0, 12) + '…' : d.name
    ),
    datasets: [{
      label: 'Value Terbaru',
      data: data.slice(0, 20).reverse().map(d => d.value),
      borderColor: CHART_COLORS.primary,
      backgroundColor: CHART_COLORS.fill,
      fill: true,
      tension: 0.4,
      pointBackgroundColor: CHART_COLORS.primary,
      pointRadius: 4,
    }]
  };

  // ── Chart data — Bar (statistik per kategori) ─────────────────────
  const barData = {
    labels: stats.map(s => s.category),
    datasets: [
      {
        label: 'Rata-rata',
        data: stats.map(s => s.avg),
        backgroundColor: CHART_COLORS.primary,
        borderRadius: 6,
      },
      {
        label: 'Maksimum',
        data: stats.map(s => s.max),
        backgroundColor: CHART_COLORS.secondary,
        borderRadius: 6,
      }
    ]
  };

  // ── Computed stats ─────────────────────────────────────────────────
  const totalRecords  = pagination.total;
  const totalCats     = stats.length;
  const latestValue   = data[0]?.value?.toFixed(2) ?? '—';
  const overallAvg    = stats.length
    ? (stats.reduce((s, x) => s + x.avg, 0) / stats.length).toFixed(2)
    : '—';

  // ──────────────────────────────────────────────────────────────────
  return (
    <div className="dashboard">

      {/* Header */}
      <div className="header">
        <div className="header-title">
          <h1>📊 AWS Data Dashboard</h1>
          <p>Amplify · Elastic Beanstalk · Lambda · RDS PostgreSQL</p>
        </div>
        <div className="header-badge">🟢 Live · Auto-refresh 30s</div>
      </div>

      {/* Stats Cards */}
      <div className="stats-grid">
        <StatCard label="Total Data" value={totalRecords.toLocaleString()} sub="semua record" />
        <StatCard label="Kategori" value={totalCats} sub="kategori unik" />
        <StatCard label="Nilai Terbaru" value={latestValue} sub={data[0]?.name || '—'} />
        <StatCard label="Rata-rata Global" value={overallAvg} sub="semua kategori" />
      </div>

      {/* Form Input */}
      <div className="card">
        <div className="card-title">📥 Input Data Baru</div>
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label>Nama / Label</label>
              <input
                className="form-input"
                placeholder="contoh: sensor-suhu-1"
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div className="form-group" style={{ maxWidth: 140 }}>
              <label>Nilai (angka)</label>
              <input
                className="form-input"
                type="number"
                step="0.01"
                placeholder="28.5"
                value={form.value}
                onChange={e => setForm({ ...form, value: e.target.value })}
                required
              />
            </div>
            <div className="form-group" style={{ maxWidth: 160 }}>
              <label>Kategori</label>
              <select
                className="form-select"
                value={form.category}
                onChange={e => setForm({ ...form, category: e.target.value })}
              >
                <option value="sensor">Sensor</option>
                <option value="metric">Metric</option>
                <option value="log">Log</option>
                <option value="temperature">Temperature</option>
                <option value="humidity">Humidity</option>
                <option value="pressure">Pressure</option>
              </select>
            </div>
            <div style={{ paddingBottom: 0 }}>
              <label style={{ fontSize: '0.8rem', color: 'transparent', display: 'block' }}>.</label>
              <button className="btn-submit" type="submit" disabled={submitting}>
                {submitting ? '⏳ Menyimpan...' : '➕ Simpan Data'}
              </button>
            </div>
          </div>
          {message && (
            <div className={`alert alert-${message.type}`}>{message.text}</div>
          )}
        </form>
      </div>

      {/* Charts */}
      <div className="charts-grid">
        <div className="card">
          <div className="card-title">📈 Line Chart — 20 Data Terbaru</div>
          {data.length > 0
            ? <Line data={lineData} options={CHART_OPTIONS_BASE} />
            : <div className="empty-state"><h3>Belum ada data</h3><p>Coba input data menggunakan form di atas</p></div>
          }
        </div>
        <div className="card">
          <div className="card-title">📊 Bar Chart — Statistik per Kategori</div>
          {stats.length > 0
            ? <Bar data={barData} options={CHART_OPTIONS_BASE} />
            : <div className="empty-state"><h3>Belum ada statistik</h3></div>
          }
        </div>
      </div>

      {/* Data Table */}
      <div className="card">
        <div className="card-title">🗃️ Data Terbaru — {totalRecords.toLocaleString()} total record</div>

        {loading ? (
          <div className="loading-overlay">
            <div className="spinner" />
            <span>Memuat data...</span>
          </div>
        ) : data.length === 0 ? (
          <div className="empty-state">
            <h3>Belum ada data</h3>
            <p>Masukkan data pertama menggunakan form di atas</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Nama</th>
                  <th>Nilai</th>
                  <th>Kategori</th>
                  <th>Waktu</th>
                </tr>
              </thead>
              <tbody>
                {data.map(row => (
                  <tr key={row.id}>
                    <td className="text-muted">#{row.id}</td>
                    <td style={{ fontWeight: 500 }}>{row.name}</td>
                    <td style={{ color: '#34d399', fontFamily: 'monospace' }}>{row.value.toFixed(2)}</td>
                    <td><span className="badge">{row.category}</span></td>
                    <td className="text-muted">
                      {new Date(row.created_at).toLocaleString('id-ID', {
                        day: '2-digit', month: 'short',
                        hour: '2-digit', minute: '2-digit'
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <button className="btn-refresh" onClick={fetchData} disabled={loading}>
          🔄 {loading ? 'Memuat...' : 'Refresh Data'}
        </button>
      </div>

    </div>
  );
}
