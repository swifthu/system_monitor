package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Config represents the system monitor configuration
type Config struct {
	RefreshInterval int           `json:"refresh_interval"` // seconds
	HistorySize     int           `json:"history_size"`
	DiskPaths       []string      `json:"disk_paths"`       // monitored disk mount points
	NetworkIfaces   []string      `json:"network_ifaces"`  // monitored network interfaces
	Metrics         MetricsConfig `json:"metrics"`
}

// MetricsConfig holds configuration for metrics persistence
type MetricsConfig struct {
	Enabled        bool   `json:"enabled"`
	WriteInterval  int    `json:"write_interval"`   // seconds, default 60
	RetentionDays  int    `json:"retention_days"`   // default 30
	DBPath         string `json:"db_path"`          // default "~/.system_monitor/metrics.db"
}

// GetMetricsDefaults returns the default metrics configuration
func (c *Config) GetMetricsDefaults() MetricsConfig {
	return MetricsConfig{
		Enabled:        true,
		WriteInterval:  60,
		RetentionDays:  30,
		DBPath:         "~/.system_monitor/metrics.db",
	}
}

// DefaultConfig returns the default configuration
func DefaultConfig() *Config {
	return &Config{
		RefreshInterval: 1,
		HistorySize:     60,
		DiskPaths:       []string{"/"},
		NetworkIfaces:   []string{},
	}
}

// Load reads configuration from config.json
// Searches in ./config.json first, then $HOME/.config/system-monitor/config.json
// Returns a 503 error if config file cannot be found or parsed
func Load() (*Config, error) {
	// Try current directory first
	configPaths := []string{
		"./config.json",
		"$HOME/.config/system-monitor/config.json",
	}

	var configData []byte
	var err error

	for _, path := range configPaths {
		// Expand HOME if present
		if strings.HasPrefix(path, "$HOME/") {
			home := os.Getenv("HOME")
			if home == "" {
				continue
			}
			path = filepath.Join(home, path[6:])
		}

		configData, err = os.ReadFile(path)
		if err == nil {
			break
		}
	}

	if configData == nil {
		return nil, fmt.Errorf("config file not found")
	}

	var cfg Config
	if err := json.Unmarshal(configData, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config: %w", err)
	}

	// Apply defaults for missing fields
	if cfg.RefreshInterval <= 0 {
		cfg.RefreshInterval = 1
	}
	if cfg.HistorySize <= 0 {
		cfg.HistorySize = 60
	}
	if cfg.DiskPaths == nil {
		cfg.DiskPaths = []string{"/"}
	}
	if cfg.NetworkIfaces == nil {
		cfg.NetworkIfaces = []string{}
	}

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

	return &cfg, nil
}
