# Historical Trends & UI Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SQLite metrics persistence (30-day retention) + frosted glass dark/light theme + Canvas trend charts + new DASHBOARD tab

**Architecture:** Go backend writes batch snapshots to SQLite every N seconds; frontend fetches time-range queries via new API; single self-contained HTML file with embedded CSS/JS, custom Canvas charts (no external lib).

**Tech Stack:** Go (modernc.org/sqlite), native Canvas 2D, CSS variables, localStorage

---

## File Map

| File | Change |
|------|--------|
| `config/config.go` | Add `MetricsConfig` struct, merge into `Config` |
| `config.json` | Add `metrics` section |
| `collector/metrics.go` | **CREATE** — SQLite open, batch write, retention purge, close |
| `api/handlers.go` | Add `/api/metrics/query`, `/api/metrics/list` handlers |
| `frontend/index.html` | Full refactor — CSS variables, glass cards, theme toggle, DASHBOARD tab, Canvas charts |
| `main.go` | Init metrics writer on startup, close on shutdown |

---

## Task 1: Metrics DB Schema & Retention

**Files:**
- Create: `collector/metrics.go`
- Test: `tests/metrics_test.go`

- [ ] **Step 1: Create metrics.go with DB initialization and retention**

```go
// collector/metrics.go
package collector

import (
    "database/sql"
    "fmt"
    "os"
    "path/filepath"
    "time"

    _ "modernc.org/sqlite"
)

type MetricsDB struct {
    db *sql.DB
}

func NewMetricsDB(dbPath string) (*MetricsDB, error) {
    // Expand ~
    if dbPath[0] == '~' {
        home, _ := os.UserHomeDir()
        dbPath = filepath.Join(home, dbPath[1:])
    }

    // Ensure directory exists
    dir := filepath.Dir(dbPath)
    if err := os.MkdirAll(dir, 0755); err != nil {
        return nil, fmt.Errorf("create metrics dir: %w", err)
    }

    db, err := sql.Open("sqlite", dbPath)
    if err != nil {
        return nil, fmt.Errorf("open db: %w", err)
    }

    m := &MetricsDB{db: db}
    if err := m.migrate(); err != nil {
        db.Close()
        return nil, fmt.Errorf("migrate: %w", err)
    }

    return m, nil
}

func (m *MetricsDB) migrate() error {
    schema := `
    CREATE TABLE IF NOT EXISTS metrics (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   INTEGER NOT NULL,
        source      TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        value       REAL NOT NULL,
        tags        TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_metrics_ts      ON metrics(timestamp);
    CREATE INDEX IF NOT EXISTS idx_metrics_name_ts  ON metrics(metric_name, timestamp);
    `
    _, err := m.db.Exec(schema)
    return err
}

// Purge deletes metrics older than retentionDays
func (m *MetricsDB) Purge(retentionDays int) error {
    cutoff := time.Now().Unix() - int64(retentionDays*86400)
    _, err := m.db.Exec("DELETE FROM metrics WHERE timestamp < ?", cutoff)
    return err
}

func (m *MetricsDB) Close() error {
    return m.db.Close()
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd /Users/jimmyhu/Documents/CC/Projects/system_monitor && go build ./...`
Expected: No errors

- [ ] **Step 3: Test purge logic (inline manual test)**

Run: create temp DB, insert old record, call Purge(0), verify deleted

```go
// Add to metrics.go temporarily for testing:
func TestPurge(t *testing.T) {
    db, err := NewMetricsDB("/tmp/test_metrics.db")
    if err != nil {
        t.Fatal(err)
    }
    defer os.Remove("/tmp/test_metrics.db")
    defer db.Close()

    // Insert with old timestamp (1 day ago)
    oldTs := time.Now().Add(-24 * time.Hour).Unix()
    _, err = db.db.Exec(
        "INSERT INTO metrics (timestamp, source, metric_name, value, tags) VALUES (?, ?, ?, ?, ?)",
        oldTs, "system", "cpu_percent", 50.0, "{}",
    )
    if err != nil {
        t.Fatal(err)
    }

    if err := db.Purge(0); err != nil {
        t.Fatal(err)
    }

    var count int
    db.db.QueryRow("SELECT COUNT(*) FROM metrics").Scan(&count)
    if count != 0 {
        t.Errorf("expected 0 rows after purge, got %d", count)
    }
}
```

Run: `go test -run TestPurge ./collector/`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add collector/metrics.go
git commit -m "feat(metrics): add SQLite metrics DB with migration and retention

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: Config — Add MetricsConfig

**Files:**
- Modify: `config/config.go:1-50`
- Modify: `config.json`

- [ ] **Step 1: Read config/config.go to see current struct**

```go
type Config struct {
    RefreshInterval int      `json:"refresh_interval"`
    HistorySize     int      `json:"history_size"`
    DiskPaths       []string `json:"disk_paths"`
    NetworkIfaces   []string `json:"network_ifaces"`
}
```

- [ ] **Step 2: Add MetricsConfig struct and merge into Config**

Add after the existing Config struct:

```go
type MetricsConfig struct {
    Enabled        bool   `json:"enabled"`
    WriteInterval  int    `json:"write_interval"`   // seconds, default 60
    RetentionDays  int    `json:"retention_days"`   // default 30
    DBPath         string `json:"db_path"`          // default "~/.system_monitor/metrics.db"
}

func (c *Config) GetMetricsDefaults() MetricsConfig {
    return MetricsConfig{
        Enabled:        true,
        WriteInterval:  60,
        RetentionDays:  30,
        DBPath:         "~/.system_monitor/metrics.db",
    }
}
```

In `Load()`, after `json.Unmarshal` into `Config`, add:

```go
    // Merge metrics config with defaults
    if cfg.Metrics.Enabled {
        defaults := cfg.GetMetricsDefaults()
        if cfg.Metrics.WriteInterval == 0 {
            cfg.Metrics.WriteInterval = defaults.WriteInterval
        }
        if cfg.Metrics.RetentionDays == 0 {
            cfg.Metrics.RetentionDays = defaults.RetentionDays
        }
        if cfg.Metrics.DBPath == "" {
            cfg.Metrics.DBPath = defaults.DBPath
        }
    }
```

- [ ] **Step 3: Update config.json**

Add `metrics` section:

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

- [ ] **Step 4: Verify it compiles**

Run: `go build ./...`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add config/config.go config.json
git commit -m "config: add metrics persistence config

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Metrics Writer — Batch Insert

**Files:**
- Modify: `collector/metrics.go`

- [ ] **Step 1: Add BatchWrite method**

Add to `MetricsDB`:

```go
// MetricPoint represents a single metric data point
type MetricPoint struct {
    Timestamp  int64
    Source    string
    MetricName string
    Value     float64
    Tags      string
}

// BatchWrite inserts multiple metrics in a single transaction
func (m *MetricsDB) BatchWrite(points []MetricPoint) error {
    if len(points) == 0 {
        return nil
    }
    tx, err := m.db.Begin()
    if err != nil {
        return err
    }
    defer tx.Rollback()

    stmt, err := tx.Prepare(
        "INSERT INTO metrics (timestamp, source, metric_name, value, tags) VALUES (?, ?, ?, ?, ?)",
    )
    if err != nil {
        return err
    }
    defer stmt.Close()

    for _, p := range points {
        if _, err := stmt.Exec(p.Timestamp, p.Source, p.MetricName, p.Value, p.Tags); err != nil {
            return err
        }
    }

    return tx.Commit()
}
```

- [ ] **Step 2: Add Query method for API**

```go
// QueryMetrics fetches metrics for a given name and time range
func (m *MetricsDB) QueryMetrics(metricName string, from, to int64, source string) ([]MetricPoint, error) {
    var rows *sql.Rows
    var err error

    if source != "" {
        rows, err = m.db.Query(
            "SELECT timestamp, value FROM metrics WHERE metric_name = ? AND timestamp >= ? AND timestamp <= ? AND source = ? ORDER BY timestamp ASC",
            metricName, from, to, source,
        )
    } else {
        rows, err = m.db.Query(
            "SELECT timestamp, value FROM metrics WHERE metric_name = ? AND timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC",
            metricName, from, to,
        )
    }
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var points []MetricPoint
    for rows.Next() {
        var p MetricPoint
        p.MetricName = metricName
        if err := rows.Scan(&p.Timestamp, &p.Value); err != nil {
            return nil, err
        }
        points = append(points, p)
    }
    return points, rows.Err()
}

// ListMetricNames returns all distinct metric_name values
func (m *MetricsDB) ListMetricNames() ([]string, error) {
    rows, err := m.db.Query("SELECT DISTINCT metric_name FROM metrics ORDER BY metric_name")
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var names []string
    for rows.Next() {
        var name string
        if err := rows.Scan(&name); err != nil {
            return nil, err
        }
        names = append(names, name)
    }
    return names, rows.Err()
}
```

- [ ] **Step 3: Verify compiles**

Run: `go build ./...`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add collector/metrics.go
git commit -m "feat(metrics): add BatchWrite and QueryMetrics methods

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Metrics Collector — Hook Into System Snapshot

**Files:**
- Modify: `collector/collector.go`
- Modify: `collector/types.go`

- [ ] **Step 1: Add MetricsCollector type to collector.go**

Add near the Collector struct:

```go
// MetricsCollector periodically writes snapshots to SQLite
type MetricsCollector struct {
    db           *MetricsDB
    collector    *Collector
    writeInterval time.Duration
    stopCh       chan struct{}
    doneCh       chan struct{}
}

func NewMetricsCollector(col *Collector, db *MetricsDB, writeIntervalSec int) *MetricsCollector {
    return &MetricsCollector{
        db:           db,
        collector:    col,
        writeInterval: time.Duration(writeIntervalSec) * time.Second,
        stopCh:       make(chan struct{}),
        doneCh:       make(chan struct{}),
    }
}

func (mc *MetricsCollector) Start(ctx context.Context) {
    go func() {
        defer close(mc.doneCh)
        ticker := time.NewTicker(mc.writeInterval)
        defer ticker.Stop()

        // Write immediately on start
        mc.writeSnapshot()

        for {
            select {
            case <-ticker.C:
                mc.writeSnapshot()
            case <-mc.stopCh:
                return
            case <-ctx.Done():
                return
            }
        }
    }()
}

func (mc *MetricsCollector) Stop() {
    close(mc.stopCh)
    <-mc.doneCh
}

func (mc *MetricsCollector) writeSnapshot() {
    snap := mc.collector.Cache().Get()
    if snap == nil {
        return
    }

    now := snap.Timestamp
    if now == 0 {
        now = time.Now().Unix()
    }

    var points []MetricPoint

    // CPU aggregate (index 0)
    if len(snap.CPU) > 0 {
        cpu := snap.CPU[0]
        points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "cpu_percent", Value: cpu.TotalPercent, Tags: "{}"})
        points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "cpu_user", Value: cpu.User, Tags: "{}"})
        points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "cpu_system", Value: cpu.System, Tags: "{}"})
        points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "cpu_idle", Value: cpu.Idle, Tags: "{}"})
    }

    // Memory
    points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "memory_used", Value: float64(snap.Memory.Used), Tags: "{}"})
    points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "memory_free", Value: float64(snap.Memory.Free), Tags: "{}"})
    points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "memory_percent", Value: snap.Memory.UsedPercent, Tags: "{}"})

    // Power
    points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "gpu_power", Value: snap.Power.GPUPower, Tags: "{}"})
    points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "cpu_power", Value: snap.Power.CPUPower, Tags: "{}"})
    points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "ram_power", Value: snap.Power.RAMPower, Tags: "{}"})
    points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "sys_power", Value: snap.Power.SYSPower, Tags: "{}"})

    // Network
    for _, n := range snap.Network {
        tags := fmt.Sprintf(`{"iface":"%s"}`, n.Interface)
        points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "network_rx_bytes", Value: float64(n.RxBytes), Tags: tags})
        points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "network_tx_bytes", Value: float64(n.TxBytes), Tags: tags})
    }

    // Disk
    for _, d := range snap.Disk {
        tags := fmt.Sprintf(`{"path":"%s"}`, d.Path)
        points = append(points, MetricPoint{Timestamp: now, Source: "system", MetricName: "disk_used_percent", Value: d.UsedPercent, Tags: tags})
    }

    mc.db.BatchWrite(points)
}
```

- [ ] **Step 2: Hook into main.go**

Read current main.go and add:

```go
// After col.Start(ctx), add:
var metricsCol *collector.MetricsCollector
if cfg.Metrics.Enabled {
    db, err := collector.NewMetricsDB(cfg.Metrics.DBPath)
    if err != nil {
        log.Printf("Metrics DB init failed: %v", err)
    } else {
        if err := db.Purge(cfg.Metrics.RetentionDays); err != nil {
            log.Printf("Metrics purge failed: %v", err)
        }
        metricsCol = collector.NewMetricsCollector(col, db, cfg.Metrics.WriteInterval)
        metricsCol.Start(ctx)
    }
}

// Before col.Stop(), add:
if metricsCol != nil {
    metricsCol.Stop()
}
```

- [ ] **Step 3: Verify compiles**

Run: `go build ./...`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add main.go collector/collector.go collector/types.go
git commit -m "feat(metrics): hook MetricsCollector into system snapshots

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: API Endpoints — /api/metrics/query & /api/metrics/list

**Files:**
- Modify: `api/handlers.go`

- [ ] **Step 1: Add MetricsHandler struct and route registration**

Read `api/handlers.go` first. Add to `NewHandler`:

```go
h.mux.HandleFunc("/api/metrics/query", h.handleMetricsQuery)
h.mux.HandleFunc("/api/metrics/list", h.handleMetricsList)
```

Add handler methods:

```go
// handleMetricsQuery returns time-series data
// GET /api/metrics/query?metric=cpu_percent&from=ts&to=ts&source=system
func (h *Handler) handleMetricsQuery(w http.ResponseWriter, r *http.Request) {
    metric := r.URL.Query().Get("metric")
    source := r.URL.Query().Get("source")
    fromStr := r.URL.Query().Get("from")
    toStr := r.URL.Query().Get("to")

    if metric == "" || fromStr == "" || toStr == "" {
        http.Error(w, "metric, from, to required", http.StatusBadRequest)
        return
    }

    from, err := strconv.ParseInt(fromStr, 10, 64)
    if err != nil {
        http.Error(w, "invalid from", http.StatusBadRequest)
        return
    }
    to, err := strconv.ParseInt(toStr, 10, 64)
    if err != nil {
        http.Error(w, "invalid to", http.StatusBadRequest)
        return
    }

    if h.metricsDB == nil {
        http.Error(w, "metrics not enabled", http.StatusServiceUnavailable)
        return
    }

    points, err := h.metricsDB.QueryMetrics(metric, from, to, source)
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    json.NewEncoder(w).Encode(map[string]interface{}{
        "metric": metric,
        "from":   from,
        "to":     to,
        "points": points,
    })
}

// handleMetricsList returns all available metric names
func (h *Handler) handleMetricsList(w http.ResponseWriter, r *http.Request) {
    if h.metricsDB == nil {
        http.Error(w, "metrics not enabled", http.StatusServiceUnavailable)
        return
    }

    names, err := h.metricsDB.ListMetricNames()
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    json.NewEncoder(w).Encode(map[string]interface{}{
        "metrics": names,
    })
}
```

- [ ] **Step 2: Add metricsDB field to Handler struct**

In `api/handlers.go`, modify Handler struct:

```go
type Handler struct {
    collector  *collector.Collector
    metricsDB  *collector.MetricsDB  // nil if metrics disabled
    mux        *http.ServeMux
}
```

Update `NewHandler` signature to accept `*collector.MetricsDB`:

```go
func NewHandler(col *collector.Collector, metricsDB *collector.MetricsDB) http.Handler
```

Update main.go call site.

- [ ] **Step 3: Verify compiles**

Run: `go build ./...`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add api/handlers.go main.go
git commit -m "feat(api: add /api/metrics/query and /api/metrics/list

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: Frontend — CSS Variables & Frosted Glass Theme

**Files:**
- Modify: `frontend/index.html` (CSS section only)

- [ ] **Step 1: Replace CSS variables block**

Find the `<style>` section in index.html. Replace with:

```css
:root {
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
  --tab-bg: rgba(255, 255, 255, 0.06);
  --tab-active: rgba(255, 255, 255, 0.12);
  --scrollbar: rgba(255, 255, 255, 0.1);
  --scrollbar-hover: rgba(255, 255, 255, 0.2);
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
  --tab-bg: rgba(0, 0, 0, 0.04);
  --tab-active: rgba(0, 0, 0, 0.08);
  --scrollbar: rgba(0, 0, 0, 0.15);
  --scrollbar-hover: rgba(0, 0, 0, 0.25);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
  background: var(--bg);
  color: var(--text);
  transition: background 0.3s ease, color 0.3s ease;
  min-height: 100vh;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--scrollbar); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-hover); }

/* Header */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: var(--card-bg);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-bottom: 1px solid var(--card-border);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.3px;
}

/* Theme toggle */
.theme-toggle {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: 1px solid var(--card-border);
  background: var(--card-bg);
  color: var(--text);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  transition: all 0.2s ease;
}
.theme-toggle:hover {
  border-color: var(--accent);
  background: var(--tab-active);
}

/* Tabs */
.tabs {
  display: flex;
  gap: 8px;
  padding: 16px 24px;
  background: var(--bg);
  border-bottom: 1px solid var(--card-border);
  overflow-x: auto;
}

.tab {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid var(--card-border);
  background: var(--tab-bg);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.tab:hover {
  color: var(--text);
  background: var(--tab-active);
}

.tab.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

/* Content area */
.content {
  padding: 24px;
}

/* Glass card */
.glass-card {
  background: var(--card-bg);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--card-border);
  border-radius: 16px;
  box-shadow: var(--shadow);
  padding: 20px;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.glass-card:hover {
  transform: translateY(-2px);
  border-color: var(--accent);
  box-shadow: var(--shadow), 0 0 20px var(--accent-glow);
}

/* Grid */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

/* Card title */
.card-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

/* Value display */
.value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text);
  transition: all 0.3s ease;
}

.value-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

/* Progress bar */
.progress-bar {
  height: 6px;
  background: var(--card-border);
  border-radius: 3px;
  overflow: hidden;
  margin-top: 8px;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  transition: width 0.3s ease;
  box-shadow: 0 0 8px var(--accent-glow);
}

/* Pulse animation for power indicators */
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 4px var(--accent-glow); }
  50% { box-shadow: 0 0 12px var(--accent-glow); }
}

.power-indicator {
  animation: pulse-glow 2s ease-in-out infinite;
}

/* Tab content animation */
.tab-content {
  animation: fadeSlideIn 0.2s ease-out;
}

@keyframes fadeSlideIn {
  from { opacity: 0; transform: translateX(8px); }
  to { opacity: 1; transform: translateX(0); }
}

/* Number transition */
.metric-value {
  transition: all 0.3s ease;
}

/* Canvas chart */
canvas {
  display: block;
  width: 100%;
  margin-top: 8px;
}
```

- [ ] **Step 2: Add theme toggle button to header HTML**

Find the header div in index.html. Add after the title span:

```html
<button class="theme-toggle" id="themeToggle" title="Toggle theme">🌙</button>
```

- [ ] **Step 3: Add theme toggle JavaScript**

Find the `<script>` section at the bottom of index.html. Add at the top:

```js
// Theme management
function initTheme() {
    const saved = localStorage.getItem('theme') || 'dark';
    document.documentElement.className = saved;
    updateThemeIcon(saved);
}

function updateThemeIcon(theme) {
    const btn = document.getElementById('themeToggle');
    if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
}

function toggleTheme() {
    const current = document.documentElement.className;
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.className = next;
    localStorage.setItem('theme', next);
    updateThemeIcon(next);
}

// Wire up
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    document.getElementById('themeToggle')?.addEventListener('click', toggleTheme);
});
```

- [ ] **Step 4: Verify the page loads**

Run: `go build -o server . && ./server &` then `sleep 1 && curl -s http://localhost:8001/ | head -50`
Expected: HTML page with CSS variables present

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html
git commit -m "feat(ui): frosted glass dark/light theme with CSS variables

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Frontend — Canvas Chart Library

**Files:**
- Modify: `frontend/index.html` (add charts.js content inline)

- [ ] **Step 1: Add Canvas chart rendering code to index.html `<script>`**

Add before the existing JavaScript:

```js
// ========== Canvas Chart Library ==========
class LineChart {
    constructor(canvas, config) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.config = {
            color: '#58a6ff',
            fillColor: 'rgba(88, 166, 255, 0.15)',
            unit: '',
            max: undefined,
            min: 0,
            animated: true,
            ...config
        };
        this.data = [];
        this.animationProgress = 0;
        this.animationFrame = null;
    }

    setData(points) {
        this.data = points || [];
        if (this.config.animated) {
            this.animateIn();
        } else {
            this.draw(1);
        }
    }

    animateIn() {
        if (this.animationFrame) cancelAnimationFrame(this.animationFrame);
        this.animationProgress = 0;
        const startTime = performance.now();
        const duration = 300;

        const step = (now) => {
            this.animationProgress = Math.min((now - startTime) / duration, 1);
            this.draw(this.easeOut(this.animationProgress));
            if (this.animationProgress < 1) {
                this.animationFrame = requestAnimationFrame(step);
            }
        };
        this.animationFrame = requestAnimationFrame(step);
    }

    easeOut(t) {
        return 1 - Math.pow(1 - t, 3);
    }

    draw(progress) {
        const { canvas, ctx, config, data } = this;
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();

        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const W = rect.width;
        const H = rect.height;
        const padding = { top: 10, right: 10, bottom: 24, left: 40 };
        const chartW = W - padding.left - padding.right;
        const chartH = H - padding.top - padding.bottom;

        // Clear
        ctx.clearRect(0, 0, W, H);

        if (data.length < 2) {
            ctx.fillStyle = config.color;
            ctx.font = '12px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Not enough data', W / 2, H / 2);
            return;
        }

        // Calculate value range
        let max = config.max;
        let min = config.min;
        if (max === undefined) {
            max = Math.max(...data.map(d => d.value));
            if (max === min) max = min + 1;
        }

        // Grid lines
        ctx.strokeStyle = 'rgba(255,255,255,0.06)';
        ctx.lineWidth = 1;
        ctx.font = '10px -apple-system, sans-serif';
        ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#8b949e';
        ctx.textAlign = 'right';

        for (let i = 0; i <= 4; i++) {
            const y = padding.top + (chartH / 4) * i;
            const val = max - ((max - min) / 4) * i;
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(W - padding.right, y);
            ctx.stroke();
            ctx.fillText(val.toFixed(1) + config.unit, padding.left - 6, y + 3);
        }

        // X-axis labels (time)
        if (data.length > 0) {
            ctx.textAlign = 'center';
            const first = new Date(data[0].timestamp * 1000);
            const last = new Date(data[data.length - 1].timestamp * 1000);
            ctx.fillText(this.formatTime(first), padding.left, H - 4);
            ctx.fillText(this.formatTime(last), W - padding.right, H - 4);
        }

        // Build path
        const pointsToDraw = data.slice(0, Math.ceil(data.length * progress));
        if (pointsToDraw.length === 0) return;

        const getX = (i) => padding.left + (i / (data.length - 1)) * chartW;
        const getY = (v) => padding.top + ((max - v) / (max - min)) * chartH;

        // Gradient fill
        const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
        gradient.addColorStop(0, config.fillColor);
        gradient.addColorStop(1, 'transparent');

        ctx.beginPath();
        pointsToDraw.forEach((d, i) => {
            const x = getX(i);
            const y = getY(d.value);
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                // Smooth curve
                const prev = pointsToDraw[i - 1];
                const prevX = getX(i - 1);
                const cpX = (prevX + x) / 2;
                ctx.bezierCurveTo(cpX, getY(prev.value), cpX, y, x, y);
            }
        });

        // Fill area
        const lastX = getX(pointsToDraw.length - 1);
        const firstX = getX(0);
        ctx.lineTo(lastX, padding.top + chartH);
        ctx.lineTo(firstX, padding.top + chartH);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();

        // Line
        ctx.beginPath();
        pointsToDraw.forEach((d, i) => {
            const x = getX(i);
            const y = getY(d.value);
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                const prev = pointsToDraw[i - 1];
                const prevX = getX(i - 1);
                const cpX = (prevX + x) / 2;
                ctx.bezierCurveTo(cpX, getY(prev.value), cpX, y, x, y);
            }
        });
        ctx.strokeStyle = config.color;
        ctx.lineWidth = 2;
        ctx.stroke();

        // Hover tooltip (show on last point)
        if (progress >= 1 && pointsToDraw.length > 0) {
            const last = pointsToDraw[pointsToDraw.length - 1];
            const x = getX(pointsToDraw.length - 1);
            const y = getY(last.value);

            // Dot
            ctx.beginPath();
            ctx.arc(x, y, 4, 0, Math.PI * 2);
            ctx.fillStyle = config.color;
            ctx.fill();
            ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() || '#0d1117';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Tooltip
            const text = last.value.toFixed(1) + config.unit;
            ctx.font = '11px -apple-system, sans-serif';
            const textW = ctx.measureText(text).width;
            const tx = Math.min(x - textW / 2, W - padding.right - textW - 8);
            const ty = y - 28;

            ctx.fillStyle = 'rgba(0,0,0,0.8)';
            ctx.beginPath();
            ctx.roundRect(tx - 4, ty - 10, textW + 8, 18, 4);
            ctx.fill();

            ctx.fillStyle = '#fff';
            ctx.textAlign = 'left';
            ctx.fillText(text, tx, ty + 4);
        }
    }

    formatTime(date) {
        return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    }

    resize() {
        if (this.animationFrame) cancelAnimationFrame(this.animationFrame);
        this.draw(1);
    }
}
```

- [ ] **Step 2: Verify HTML still loads**

Run: `go build -o server . && ./server & sleep 1 && curl -s http://localhost:8001/ | grep -c "LineChart"`
Expected: 1 (LineChart class found)

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "feat(ui): add Canvas LineChart library with animations

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: Frontend — DASHBOARD Tab

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: Add DASHBOARD tab button**

Find the tabs div in index.html. Add before the closing `</div>`:

```html
<div class="tab active" data-tab="dashboard">DASHBOARD</div>
```

Make existing tabs initially not active (remove `class="active"` from first tab).

- [ ] **Step 2: Add DASHBOARD tab content HTML**

Find the content div. Add as the FIRST child:

```html
<div id="tab-dashboard" class="tab-panel" style="display:none;">
    <div class="dashboard-header">
        <div class="dashboard-title">System Overview</div>
        <div class="time-range-selector">
            <button class="range-btn active" data-range="1">1H</button>
            <button class="range-btn" data-range="6">6H</button>
            <button class="range-btn" data-range="24">24H</button>
            <button class="range-btn" data-range="168">7D</button>
            <button class="range-btn" data-range="720">30D</button>
        </div>
    </div>
    <div class="dashboard-grid">
        <div class="glass-card chart-card">
            <div class="card-title">CPU Usage</div>
            <div class="value" id="dash-cpu-value">--</div>
            <canvas id="chart-cpu" height="120"></canvas>
        </div>
        <div class="glass-card chart-card">
            <div class="card-title">Memory</div>
            <div class="value" id="dash-mem-value">--</div>
            <canvas id="chart-mem" height="120"></canvas>
        </div>
        <div class="glass-card chart-card">
            <div class="card-title">Network RX</div>
            <div class="value" id="dash-net-rx-value">--</div>
            <canvas id="chart-net-rx" height="120"></canvas>
        </div>
        <div class="glass-card chart-card">
            <div class="card-title">Network TX</div>
            <div class="value" id="dash-net-tx-value">--</div>
            <canvas id="chart-net-tx" height="120"></canvas>
        </div>
        <div class="glass-card chart-card">
            <div class="card-title">GPU Power</div>
            <div class="value" id="dash-gpu-power-value">--</div>
            <canvas id="chart-gpu-power" height="120"></canvas>
        </div>
        <div class="glass-card chart-card">
            <div class="card-title">oMLX Cache Hit</div>
            <div class="value" id="dash-oml-value">--</div>
            <canvas id="chart-oml" height="120"></canvas>
        </div>
    </div>
</div>
```

- [ ] **Step 3: Add DASHBOARD styles**

Add to the CSS section:

```css
/* Dashboard */
.dashboard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.dashboard-title {
    font-size: 20px;
    font-weight: 600;
}

.time-range-selector {
    display: flex;
    gap: 6px;
}

.range-btn {
    padding: 6px 12px;
    border-radius: 6px;
    border: 1px solid var(--card-border);
    background: var(--tab-bg);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    transition: all 0.2s ease;
}

.range-btn:hover {
    color: var(--text);
    background: var(--tab-active);
}

.range-btn.active {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
}

.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
}

.chart-card {
    min-height: 200px;
}
```

- [ ] **Step 4: Add DASHBOARD JavaScript logic**

Find the tab switching code in the script section. After existing tab switching logic, add:

```js
// Dashboard state
const dashboardState = {
    range: 1, // hours
    charts: {},
    timers: []
};

// Init dashboard charts
function initDashboard() {
    const charts = [
        { id: 'chart-cpu', metric: 'cpu_percent', unit: '%', color: '#58a6ff', max: 100 },
        { id: 'chart-mem', metric: 'memory_percent', unit: '%', color: '#a371f7', max: 100 },
        { id: 'chart-net-rx', metric: 'network_rx_bytes', unit: 'B/s', color: '#3fb950', max: undefined },
        { id: 'chart-net-tx', metric: 'network_tx_bytes', unit: 'B/s', color: '#f0883e', max: undefined },
        { id: 'chart-gpu-power', metric: 'gpu_power', unit: 'W', color: '#f85149', max: undefined },
        { id: 'chart-oml', metric: 'oml_cache_hit_rate', unit: '', color: '#58a6ff', max: 1 },
    ];

    charts.forEach(cfg => {
        const canvas = document.getElementById(cfg.id);
        if (canvas) {
            dashboardState.charts[cfg.metric] = new LineChart(canvas, {
                color: cfg.color,
                unit: cfg.unit,
                max: cfg.max,
                fillColor: cfg.color.replace(')', ', 0.15)').replace('rgb', 'rgba'),
            });
        }
    });

    // Time range buttons
    document.querySelectorAll('.range-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            dashboardState.range = parseInt(btn.dataset.range);
            loadDashboardData();
        });
    });
}

// Load dashboard data from API
async function loadDashboardData() {
    const now = Math.floor(Date.now() / 1000);
    const from = now - dashboardState.range * 3600;

    const metrics = ['cpu_percent', 'memory_percent', 'network_rx_bytes', 'network_tx_bytes', 'gpu_power', 'oml_cache_hit_rate'];

    for (const metric of metrics) {
        try {
            const resp = await fetch(`/api/metrics/query?metric=${metric}&from=${from}&to=${now}`);
            if (!resp.ok) continue;
            const data = await resp.json();
            const points = (data.points || []).map(p => ({
                timestamp: p.timestamp,
                value: metric === 'oml_cache_hit_rate' ? p.value * 100 : p.value
            }));

            const chart = dashboardState.charts[metric];
            if (chart) {
                chart.setData(points);
                // Update current value badge
                if (points.length > 0) {
                    const last = points[points.length - 1].value;
                    const unit = chart.config.unit;
                    const valueEl = document.getElementById(`dash-${metric.replace(/_([rx])$/, '-$1').replace('oml_cache_hit_rate', 'oml')}-value`);
                    if (valueEl) valueEl.textContent = last.toFixed(1) + unit;
                }
            }
        } catch (e) {
            // Metrics not available yet, skip
        }
    }
}
```

- [ ] **Step 5: Wire up tab switching for DASHBOARD**

Find the existing tab switching code and ensure it handles `dashboard`:

```js
// In tab click handler:
if (tabId === 'dashboard') {
    document.querySelectorAll('.range-btn')[0]?.click(); // trigger 1H by default
    loadDashboardData();
}
```

- [ ] **Step 6: Verify HTML loads**

Run: `go build -o server . && ./server & sleep 1 && curl -s http://localhost:8001/ | grep -c "tab-dashboard"`
Expected: 1

- [ ] **Step 7: Commit**

```bash
git add frontend/index.html
git commit -m "feat(ui): add DASHBOARD tab with time-range selectable charts

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 9: Integration — Connect Everything

**Files:**
- Review all modified files
- Test end-to-end

- [ ] **Step 1: Full build test**

Run: `go build -o server . && ./server &`
Expected: Server starts without error

- [ ] **Step 2: Verify API endpoints**

```bash
# Wait 65 seconds for first metrics write (or restart to trigger)
sleep 2
curl -s "http://localhost:8001/api/metrics/list" | python3 -m json.tool
curl -s "http://localhost:8001/api/metrics/query?metric=cpu_percent&from=$(date +%s -d '1 hour ago')&to=$(date +%s)" | python3 -m json.tool
```

Expected: List returns array, query returns points array

- [ ] **Step 3: Verify UI**

Open `http://localhost:8001` in browser:
- [ ] Dark theme by default
- [ ] Theme toggle works (sun/moon icon)
- [ ] DASHBOARD tab visible
- [ ] Click DASHBOARD → charts render
- [ ] Time range buttons work
- [ ] Tab switching animates
- [ ] Cards have frosted glass effect

- [ ] **Step 4: Test theme persistence**

Toggle theme, reload page — theme should persist

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete historical trends + UI overhaul

- SQLite metrics persistence with 30-day retention
- Frosted glass dark/light theme
- Canvas trend charts in DASHBOARD tab
- Configurable via config.json

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 10: Final Verification

- [ ] **Step 1: Clean build**

Run: `go build -o server . && ./server &` + browser smoke test

- [ ] **Step 2: Check for regressions**

Existing tabs (SYSTEM, oMLX, QUOTA) all still work

- [ ] **Step 3: Verify retention works**

Kill server, restart — old data should persist across restarts
