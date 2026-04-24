# System Monitor - Historical Trends & UI Enhancement Design

**Date**: 2026-04-23
**Author**: Claude (brainstorming with user)
**Status**: Approved

---

## 1. Overview

Add two major features to the system_monitor project:

1. **Historical trending** — persist metrics to SQLite with 30-day retention, queryable via new API
2. **UI/UX overhaul** — frosted glass dark theme, theme toggle, dynamic HTML5 elements

---

## 2. Metrics Persistence

### 2.1 Storage

- **Database**: SQLite at `~/.system_monitor/metrics.db`
- **Write strategy**: Batch write every `metrics.write_interval` seconds (configurable, default 60s)
- **Retention**: 30 days, auto-purged on startup
- **No external dependencies** — pure Go `modernc.org/sqlite`

### 2.2 Schema

```sql
CREATE TABLE metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   INTEGER NOT NULL,           -- Unix seconds
    source      TEXT NOT NULL,              -- 'system' | 'oml' | 'quota'
    metric_name TEXT NOT NULL,              -- e.g. 'cpu_percent', 'memory_used'
    value       REAL NOT NULL,
    tags        TEXT                        -- JSON, e.g. {"tab":"system"}
);

CREATE INDEX idx_metrics_ts        ON metrics(timestamp);
CREATE INDEX idx_metrics_name_ts   ON metrics(metric_name, timestamp);
```

### 2.3 Config Changes (`config/config.go`)

```go
type MetricsConfig struct {
    Enabled        bool    `json:"enabled"`
    WriteInterval  int     `json:"write_interval"`   // seconds, default 60
    RetentionDays  int     `json:"retention_days"`   // default 30
    DBPath         string  `json:"db_path"`          // default "~/.system_monitor/metrics.db"
}
```

Default `config.json`:
```json
{
  "metrics": {
    "enabled": true,
    "write_interval": 60,
    "retention_days": 30,
    "db_path": "~/.system_monitor/metrics.db"
  }
}
```

### 2.4 Data Collected (per write interval)

**System tab**:
- `cpu_user`, `cpu_system`, `cpu_idle`, `cpu_percent`
- `memory_used`, `memory_free`, `memory_percent`
- `gpu_power`, `cpu_power`, `ram_power`, `sys_power`
- `disk_read_bytes`, `disk_write_bytes`
- `network_rx_bytes`, `network_tx_bytes`

**oMLX tab**:
- `oml_cache_hit_rate`
- `oml_prefill_tok_s`
- `oml_generation_tok_s`
- `oml_memory_used`

**Quota tab**:
- `quota_used_percent`
- `banwagon_data_used`, `banwagon_data_limit`

### 2.5 New API Endpoints

| Endpoint | Method | Params | Description |
|----------|--------|--------|-------------|
| `/api/metrics/query` | GET | `metric`, `from`, `to`, `source` | Range query, returns `[{timestamp, value}]` |
| `/api/metrics/list` | GET | — | List all `metric_name` values |

Query response:
```json
{
  "metric": "cpu_percent",
  "from": 1713840000,
  "to": 1713843600,
  "points": [
    {"timestamp": 1713840000, "value": 23.5},
    {"timestamp": 1713840060, "value": 24.1}
  ]
}
```

---

## 3. UI Theme System

### 3.1 CSS Variables

```css
:root {
  /* Dark (default) */
  --bg: #0d1117;
  --card-bg: rgba(255, 255, 255, 0.08);
  --card-border: rgba(255, 255, 255, 0.12);
  --text: #e6edf3;
  --text-muted: #8b949e;
  --accent: #58a6ff;
  --accent-glow: rgba(88, 166, 255, 0.4);
  --success: #3fb950;
  --warning: #d29922;
  --danger: #f85149;
  --shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

:root.light {
  --bg: #f5f5f7;
  --card-bg: rgba(255, 255, 255, 0.6);
  --card-border: rgba(0, 0, 0, 0.1);
  --text: #1d1d1f;
  --text-muted: #6e6e73;
  --accent: #0066cc;
  --accent-glow: rgba(0, 102, 204, 0.3);
  --shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}
```

### 3.2 Theme Toggle

- Button in top-right corner (sun/moon icon)
- Persisted in `localStorage`
- Toggle animates with 300ms transition

---

## 4. Frosted Glass UI

### 4.1 Card Style

```css
.glass-card {
  background: var(--card-bg);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--card-border);
  border-radius: 16px;
  box-shadow: var(--shadow);
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.glass-card:hover {
  transform: translateY(-2px);
  border-color: var(--accent);
}
```

### 4.2 Layout

- Header: Logo left, theme toggle right
- Tab bar: horizontal, frosted glass pill style
- Content area: scrollable, padding 24px
- Cards: 16px gap grid

---

## 5. Dynamic HTML5 Elements

### 5.1 Canvas Line Charts (趋势图)

- Custom Canvas 2D implementation, no external charting library
- Features:
  - Smooth cubic bezier curves
  - Gradient fill under line
  - Hover tooltip showing exact value + timestamp
  - Animated draw-in on first render (300ms ease-out per series)
  - Grid lines with labels
  - Responsive resize

**Chart configuration per metric**:
```js
{
  key: 'cpu_percent',
  label: 'CPU Usage',
  unit: '%',
  color: '#58a6ff',
  max: 100,
  sources: ['system']
}
```

### 5.2 Animations

- **Number transitions**: CSS `transition: all 0.3s ease` on value changes
- **Tab switch**: slide-in from right, 200ms
- **Progress bar pulse**: subtle glow animation on power indicators
- **Card hover**: lift + border highlight (already in glass-card style)
- **Chart data load**: points animate in sequentially

### 5.3 New DASHBOARD Tab

- Time range selector: 1H / 6H / 24H / 7D / 30D (buttons, frosted glass style)
- Grid of trend charts:
  - CPU (1H default)
  - Memory (1H)
  - Network I/O (1H)
  - GPU Power (1H)
  - oMLX cache hit rate (1H)
- Each chart card: title + current value badge + Canvas chart + time range picker

---

## 6. File Changes

| File | Change |
|------|--------|
| `config/config.go` | Add `MetricsConfig` struct, load from `config.json` |
| `config.json` | Add `metrics` section |
| `collector/metrics.go` | New file — SQLite write, retention purge, batch insert |
| `api/handlers.go` | Add `/api/metrics/query`, `/api/metrics/list` handlers |
| `frontend/index.html` | Full UI overhaul, add DASHBOARD tab |
| `frontend/style.css` | New file — CSS variables, frosted glass, animations |
| `frontend/charts.js` | New file — Canvas chart rendering |
| `frontend/theme.js` | New file — theme toggle logic |
| `main.go` | Initialize metrics collector on startup, graceful shutdown |

---

## 7. Out of Scope (YAGNI)

- Alerting / notifications
- Remote monitoring / multi-instance
- Prometheus / Grafana export
- Process-level metrics
- Mobile-specific layout (tablet+ only)

---

## 8. Acceptance Criteria

- [ ] Metrics written to SQLite at configurable interval
- [ ] 30-day old data auto-purged on startup
- [ ] `/api/metrics/query` returns correct time-series data
- [ ] Dark/light theme toggle works, preference persisted
- [ ] All cards use frosted glass effect
- [ ] DASHBOARD tab shows live trend charts
- [ ] Charts animate on load and on data update
- [ ] No external charting library dependency
- [ ] Configurable via `config.json`
