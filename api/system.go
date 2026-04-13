package api

import (
	"github.com/jimmyhu/Documents/CC/Projects/system_monitor/collector"
)

// SystemSnapshot mirrors collector.SystemSnapshot for API responses
type SystemSnapshot = collector.SystemSnapshot
type MemoryInfo = collector.MemoryInfo
type CPUInfo = collector.CPUInfo
type PowerInfo = collector.PowerInfo
type DiskInfo = collector.DiskInfo
type NetworkInfo = collector.NetworkInfo