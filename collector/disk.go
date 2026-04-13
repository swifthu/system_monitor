package collector

import (
	"os/exec"
	"regexp"
	"strconv"
	"strings"
)

// CollectDisk gathers disk usage statistics using diskutil
func CollectDisk(paths []string) ([]DiskInfo, error) {
	if len(paths) == 0 {
		paths = []string{"/"}
	}

	var result []DiskInfo
	for _, path := range paths {
		info, err := collectDiskInfo(path)
		if err != nil {
			continue
		}
		result = append(result, *info)
	}

	// If no disks found, try to get root disk at minimum
	if len(result) == 0 {
		info, err := collectDiskInfo("/")
		if err == nil {
			result = append(result, *info)
		}
	}

	return result, nil
}

// collectDiskInfo gets disk info for a specific mount point
func collectDiskInfo(path string) (*DiskInfo, error) {
	info := &DiskInfo{Path: path}

	// Use diskutil info / for root disk
	out, err := exec.Command("diskutil", "info", path).Output()
	if err != nil {
		return info, err
	}

	output := string(out)

	// Parse Volume Name
	if m := regexp.MustCompile(`Volume Name:\s*(.+)`).FindStringSubmatch(output); m != nil {
		info.Path = strings.TrimSpace(m[1])
	}

	// Parse Total Size - try "Disk Size" (for APFS container) or "Total Size"
	// Format: "245.1 GB (245107195904 Bytes)" or "Total Size: (100.0 GB)"
	if m := regexp.MustCompile(`Disk Size:\s*(\d+\.\d+)\s*([A-Z]?B)`).FindStringSubmatch(output); m != nil {
		val, _ := strconv.ParseFloat(m[1], 64)
		unit := m[2]
		info.Total = sizeToBytes(val, unit)
	} else if m := regexp.MustCompile(`Total Size:\s*\((\d+\.\d+)\s*([A-Z]?B)\)`).FindStringSubmatch(output); m != nil {
		val, _ := strconv.ParseFloat(m[1], 64)
		unit := m[2]
		info.Total = sizeToBytes(val, unit)
	}

	// Parse Free Space - try "Container Free Space" (APFS) or "Volume Free Space"
	// Format: "Container Free Space:      100.2 GB (100196646912 Bytes)"
	if m := regexp.MustCompile(`Container Free Space:\s*(\d+\.\d+)\s*([A-Z]?B)`).FindStringSubmatch(output); m != nil {
		val, _ := strconv.ParseFloat(m[1], 64)
		unit := m[2]
		info.Free = sizeToBytes(val, unit)
	} else if m := regexp.MustCompile(`Volume Free Space:\s*\((\d+\.\d+)\s*([A-Z]?B)\)`).FindStringSubmatch(output); m != nil {
		val, _ := strconv.ParseFloat(m[1], 64)
		unit := m[2]
		info.Free = sizeToBytes(val, unit)
	}

	// Calculate percentage - use Total - Free for Used (more accurate for APFS)
	if info.Total > 0 {
		info.Used = info.Total - info.Free
		info.UsedPercent = float64(info.Used) / float64(info.Total) * 100
	}

	return info, nil
}

// sizeToBytes converts a value with unit to bytes
func sizeToBytes(val float64, unit string) uint64 {
	switch unit {
	case "KB":
		val *= 1024
	case "MB":
		val *= 1024 * 1024
	case "GB":
		val *= 1024 * 1024 * 1024
	case "TB":
		val *= 1024 * 1024 * 1024 * 1024
	case "PB":
		val *= 1024 * 1024 * 1024 * 1024 * 1024
	}
	return uint64(val)
}

// CollectDiskIO gathers disk I/O statistics using iostat or diskutil
func CollectDiskIO() (readMBs, writeMBs float64, err error) {
	// Try using iostat first
	out, err := exec.Command("iostat", "-d", "-c", "2", "-w", "1").Output()
	if err == nil {
		return parseIOStat(string(out))
	}

	// Fallback: use diskutil list to get basic info
	return 0, 0, nil
}

// parseIOStat parses iostat output
func parseIOStat(output string) (readMBs, writeMBs float64, err error) {
	lines := strings.Split(output, "\n")
	for _, line := range lines {
		// Look for disk0 or similar
		if strings.Contains(line, "disk0") || strings.Contains(line, "disk1") {
			fields := strings.Fields(line)
			if len(fields) >= 3 {
				// KB/s read, KB/s write
				if r, err := strconv.ParseFloat(fields[1], 64); err == nil {
					readMBs = r / 1024
				}
				if w, err := strconv.ParseFloat(fields[2], 64); err == nil {
					writeMBs = w / 1024
				}
				return readMBs, writeMBs, nil
			}
		}
	}
	return 0, 0, nil
}
