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
