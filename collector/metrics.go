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
	if len(dbPath) > 0 && dbPath[0] == '~' {
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
