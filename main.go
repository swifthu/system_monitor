package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/jimmyhu/Documents/CC/Projects/system_monitor/api"
	"github.com/jimmyhu/Documents/CC/Projects/system_monitor/collector"
	"github.com/jimmyhu/Documents/CC/Projects/system_monitor/config"
)

func main() {
	log.SetFlags(0)
	log.SetOutput(os.Stdout)

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Printf("Config loading failed: %v, using defaults", err)
		cfg = config.DefaultConfig()
	}
	// Ensure metrics defaults are set
	if cfg.Metrics.WriteInterval == 0 {
		cfg.Metrics = cfg.GetMetricsDefaults()
	}

	// Create collector with background collection
	col := collector.NewCollector(2 * time.Second)

	// Start collector in background (must start before metrics collector references it)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go col.Start(ctx)

	var metricsDB *collector.MetricsDB
	var metricsCol *collector.MetricsCollector
	if cfg.Metrics.Enabled {
		db, err := collector.NewMetricsDB(cfg.Metrics.DBPath)
		if err != nil {
			log.Printf("Metrics DB init failed: %v", err)
		} else {
			metricsDB = db
			if err := db.Purge(cfg.Metrics.RetentionDays); err != nil {
				log.Printf("Metrics purge failed: %v", err)
			}
			metricsCol = collector.NewMetricsCollector(col, db, cfg.Metrics.WriteInterval)
			metricsCol.Start(ctx)
		}
	}

	// Create HTTP handler with collector (after metricsDB may be initialized)
	handler := api.NewHandler(col, metricsDB)

	// Create HTTP server
	srv := &http.Server{
		Addr:         ":8001",
		Handler:      handler,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	log.Printf("System Monitor starting on http://localhost%s\n", srv.Addr)

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	<-quit
	log.Println("Shutting down...")

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	if metricsCol != nil {
		metricsCol.Stop()
	}
	col.Stop()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}

	log.Println("Shutdown complete")
}
