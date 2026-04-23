package collector

import (
	"os"
	"testing"
	"time"
)

func TestMetricsDB_Purge(t *testing.T) {
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

func TestMetricsDB_Close(t *testing.T) {
	db, err := NewMetricsDB("/tmp/test_metrics2.db")
	if err != nil {
		t.Fatal(err)
	}
	defer os.Remove("/tmp/test_metrics2.db")
	db.Close() // should not panic
}
