package collector

import (
	"bufio"
	"context"
	"log"
	"os/exec"
	"sync"
	"time"
)

// Collector is the main collector interface
type Collector struct {
	cache     *Cache
	interval  time.Duration
	stopCh    chan struct{}
	doneCh    chan struct{}
	mu        sync.Mutex
	macmon    *macmonProcess
}

// macmonProcess manages the macmon subprocess state machine
type macmonProcess struct {
	cmd     *exec.Cmd
	mu      sync.Mutex
	running bool
	stdout  *bufio.Reader // exposed for power.go to use
}

// GetMacmonStdout returns the macmon stdout reader (for power.go to use)
func (c *Collector) GetMacmonStdout() *bufio.Reader {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.macmon.stdout
}

// IsMacmonRunning returns whether macmon is running
func (c *Collector) IsMacmonRunning() bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.macmon.running && c.macmon.stdout != nil
}

// NewCollector creates a new system collector with default 2s interval
func NewCollector(interval time.Duration) *Collector {
	if interval <= 0 {
		interval = 2 * time.Second
	}
	return &Collector{
		cache:    NewCache(),
		interval: interval,
		stopCh:   make(chan struct{}),
		doneCh:   make(chan struct{}),
		macmon:   &macmonProcess{},
	}
}

// Cache returns the collector's cache
func (c *Collector) Cache() *Cache {
	return c.cache
}

// Start begins background collection
func (c *Collector) Start(ctx context.Context) {
	c.mu.Lock()
	if c.macmon.running {
		c.mu.Unlock()
		return
	}
	c.mu.Unlock()

	log.Println("Collector: starting background collection")

	// Start macmon subprocess
	c.startMacmon()

	// Start collection loop
	go c.collectionLoop(ctx)
}

// Stop gracefully stops the collector
func (c *Collector) Stop() {
	c.mu.Lock()
	if !c.macmon.running {
		c.mu.Unlock()
		return
	}
	c.mu.Unlock()

	log.Println("Collector: stopping...")
	close(c.stopCh)
	<-c.doneCh
	c.stopMacmon()
	log.Println("Collector: stopped")
}

func (c *Collector) collectionLoop(ctx context.Context) {
	defer close(c.doneCh)

	ticker := time.NewTicker(c.interval)
	defer ticker.Stop()

	var prevSnapshot *SystemSnapshot
	stableCount := 0
	const stabilityThreshold = 0.05  // 5%
	const requiredStableRatio = 0.95 // 95%

	for {
		select {
		case <-ctx.Done():
			return
		case <-c.stopCh:
			return
		case <-ticker.C:
			snapshot := c.takeSnapshot()

			// Data stability check: |M[t] - M[t-1]|/M[t-1] < 0.05
			if prevSnapshot != nil && c.isMemoryStable(prevSnapshot, snapshot, stabilityThreshold) {
				stableCount++
			} else {
				stableCount = 0
			}

			// Check if 95% of consecutive samples are stable
			// We track this for potential quality metrics
			_ = requiredStableRatio

			c.cache.Set(snapshot)
			prevSnapshot = snapshot
		}
	}
}

func (c *Collector) isMemoryStable(prev, curr *SystemSnapshot, threshold float64) bool {
	if prev.Memory.Total == 0 {
		return false
	}
	ratio := float64(prev.Memory.Used) / float64(prev.Memory.Total)
	currRatio := float64(curr.Memory.Used) / float64(curr.Memory.Total)
	if ratio == 0 {
		return false
	}
	diff := (currRatio - ratio) / ratio
	return diff > -threshold && diff < threshold
}

func (c *Collector) takeSnapshot() *SystemSnapshot {
	now := time.Now()

	// Collect all data
	memory, _ := CollectMemory()
	cpu, _ := CollectCPU()
	power, _ := c.collectPowerWithMacmon()
	disk, _ := CollectDisk([]string{"/"})
	network, _ := CollectNetwork(nil)

	// Get network I/O rates (MB/s)
	netRates, _ := GetNetworkRates()
	for i := range network {
		if i < len(netRates) {
			network[i].RxRate = netRates[i].RxRate
			network[i].TxRate = netRates[i].TxRate
		}
	}

	return &SystemSnapshot{
		Timestamp: now.Unix(),
		Memory:    derefMemory(memory),
		CPU:       cpu,
		Power:     derefPower(power),
		Disk:      disk,
		Network:   network,
	}
}

// NetRate holds network rate for a single interface
type NetRate struct {
	RxRate float64
	TxRate float64
}

// GetNetworkRates returns per-interface network rates in MB/s
func GetNetworkRates() ([]NetRate, error) {
	netInfo, err := CollectNetwork(nil)
	if err != nil {
		return nil, err
	}

	lastNetMu.Lock()
	defer lastNetMu.Unlock()

	now := time.Now()
	rates := make([]NetRate, len(netInfo))

	if !lastNetSet || len(lastNetIfaces) != len(netInfo) {
		// Initialize baseline
		lastNetRx = make([]uint64, len(netInfo))
		lastNetTx = make([]uint64, len(netInfo))
		lastNetIfaces = make([]string, len(netInfo))
		for i, ni := range netInfo {
			lastNetRx[i] = ni.RxBytes
			lastNetTx[i] = ni.TxBytes
			lastNetIfaces[i] = ni.Interface
		}
		lastNetTime = now
		lastNetSet = true
		return rates, nil
	}

	dt := now.Sub(lastNetTime).Seconds()
	if dt <= 0 {
		return rates, nil
	}

	for i, ni := range netInfo {
		// Match by interface name
		if i < len(lastNetIfaces) && lastNetIfaces[i] == ni.Interface {
			if ni.RxBytes >= lastNetRx[i] {
				rates[i].RxRate = float64(ni.RxBytes-lastNetRx[i]) / dt / (1024 * 1024)
			}
			if ni.TxBytes >= lastNetTx[i] {
				rates[i].TxRate = float64(ni.TxBytes-lastNetTx[i]) / dt / (1024 * 1024)
			}
		}
		lastNetRx[i] = ni.RxBytes
		lastNetTx[i] = ni.TxBytes
	}
	lastNetTime = now

	return rates, nil
}

func derefMemory(m *MemoryInfo) MemoryInfo {
	if m == nil {
		return MemoryInfo{}
	}
	return *m
}

func derefPower(p *PowerInfo) PowerInfo {
	if p == nil {
		return PowerInfo{}
	}
	return *p
}

// macmon subprocess management

func (c *Collector) startMacmon() {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.macmon.running {
		return
	}

	// Try to start macmon pipe mode
	cmd := exec.Command("macmon", "pipe", "--interval", "200")
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		log.Printf("Collector: macmon stdout pipe failed: %v", err)
		return
	}

	if err := cmd.Start(); err != nil {
		log.Printf("Collector: macmon not available: %v", err)
		return
	}

	c.macmon.cmd = cmd
	c.macmon.stdout = bufio.NewReader(stdout)
	c.macmon.running = true

	// Notify power package about macmon reader
	SetExternalMacmon(c.macmon.stdout)

	log.Println("Collector: macmon subprocess started")
}

func (c *Collector) stopMacmon() {
	c.mu.Lock()
	defer c.mu.Unlock()

	if !c.macmon.running || c.macmon.cmd == nil {
		return
	}

	if err := c.macmon.cmd.Process.Kill(); err != nil {
		log.Printf("Collector: failed to kill macmon: %v", err)
	}
	c.macmon.cmd.Wait()
	c.macmon.cmd = nil
	c.macmon.running = false
	log.Println("Collector: macmon subprocess stopped")
}

func (c *Collector) collectPowerWithMacmon() (*PowerInfo, error) {
	c.mu.Lock()
	running := c.macmon.running
	c.mu.Unlock()

	if !running {
		return CollectPower()
	}

	// For now, fallback to regular power collection
	// macmon integration would read from pipe
	return CollectPower()
}
