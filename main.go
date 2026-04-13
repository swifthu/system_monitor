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
)

func main() {
	log.SetFlags(0)
	log.SetOutput(os.Stdout)

	// Create collector with background collection
	col := collector.NewCollector(2 * time.Second)

	// Create HTTP handler with collector
	handler := api.NewHandler(col)

	// Create HTTP server
	srv := &http.Server{
		Addr:         ":8001",
		Handler:      handler,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start collector in background
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go col.Start(ctx)

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

	col.Stop()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}

	log.Println("Shutdown complete")
}
