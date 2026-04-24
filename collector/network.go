package collector

import (
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Interface blacklist for filtering loopback and virtual interfaces
var ignoredInterfaces = map[string]bool{
	"lo0":   true,
	"utun":  true,
	"ap":    true,
	"awdl":  true,
	"bridge": true,
	"llw":   true,
	"gif0":  true,
	"stf0":  true,
	"pktap0": true,
}

// CollectNetwork gathers network I/O statistics using netstat -ib
func CollectNetwork(ifaces []string) ([]NetworkInfo, error) {
	out, err := exec.Command("netstat", "-ib").Output()
	if err != nil {
		return nil, err
	}

	var result []NetworkInfo
	lines := strings.Split(string(out), "\n")

	// Track seen interfaces to avoid duplicates (netstat -ib outputs multiple lines per interface)
	seen := make(map[string]bool)

	// Skip header line
	for i := 1; i < len(lines); i++ {
		line := strings.TrimSpace(lines[i])
		if line == "" {
			continue
		}

		fields := strings.Fields(line)
		if len(fields) < 10 {
			continue
		}

		name := fields[0]
		if ignoredInterfaces[name] {
			continue
		}

		// Skip duplicate interface names (netstat -ib outputs multiple rows per interface)
		if seen[name] {
			continue
		}

		// Filter by specific interfaces if provided
		if len(ifaces) > 0 {
			found := false
			for _, iface := range ifaces {
				if iface == name || iface == "*" {
					found = true
					break
				}
			}
			if !found {
				continue
			}
		}

		info := NetworkInfo{Interface: name}

		// parts[4] = Ipkts, parts[6] = Ibytes, parts[7] = Opkts, parts[9] = Obytes
		if v, err := strconv.ParseUint(fields[4], 10, 64); err == nil {
			info.RxPackets = v
		}
		if v, err := strconv.ParseUint(fields[6], 10, 64); err == nil {
			info.RxBytes = v
		}
		if v, err := strconv.ParseUint(fields[7], 10, 64); err == nil {
			info.TxPackets = v
		}
		if v, err := strconv.ParseUint(fields[9], 10, 64); err == nil {
			info.TxBytes = v
		}

		seen[name] = true
		result = append(result, info)
	}

	return result, nil
}

// lastNetIO stores the last byte counts for calculating rates
var (
	lastNetMu       sync.Mutex
	lastNetRx       []uint64
	lastNetTx       []uint64
	lastNetIfaces   []string
	lastNetTime     time.Time
	lastNetSet      bool
)

// GetNetworkIORate returns total network receive/send rates in MB/s (deprecated, use GetNetworkRates)
func GetNetworkIORate() (recvMBs, sentMBs float64, err error) {
	netInfo, err := CollectNetwork(nil)
	if err != nil {
		return 0, 0, err
	}

	var totalRx, totalTx uint64
	for _, ni := range netInfo {
		totalRx += ni.RxBytes
		totalTx += ni.TxBytes
	}

	lastNetMu.Lock()
	defer lastNetMu.Unlock()

	now := time.Now()
	if !lastNetSet || len(lastNetRx) == 0 {
		lastNetRx = []uint64{totalRx}
		lastNetTx = []uint64{totalTx}
		lastNetIfaces = []string{"total"}
		lastNetTime = now
		lastNetSet = true
		return 0, 0, nil
	}

	dt := now.Sub(lastNetTime).Seconds()
	if dt <= 0 {
		return 0, 0, nil
	}

	if totalRx >= lastNetRx[0] && totalTx >= lastNetTx[0] {
		recvMBs = float64(totalRx-lastNetRx[0]) / dt / (1024 * 1024)
		sentMBs = float64(totalTx-lastNetTx[0]) / dt / (1024 * 1024)
	}

	lastNetRx[0] = totalRx
	lastNetTx[0] = totalTx
	lastNetTime = now

	return recvMBs, sentMBs, nil
}

// ResetNetworkIO resets the network I/O baseline
func ResetNetworkIO() {
	lastNetMu.Lock()
	defer lastNetMu.Unlock()
	lastNetSet = false
	lastNetRx = nil
	lastNetTx = nil
	lastNetIfaces = nil
}
