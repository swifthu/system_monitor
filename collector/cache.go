package collector

import (
	"sync"
	"time"
)

// Cache stores the latest system snapshot with thread-safe access
type Cache struct {
	mu        sync.Mutex
	snapshot  *SystemSnapshot
	updatedAt time.Time
}

// NewCache creates a new Cache instance
func NewCache() *Cache {
	return &Cache{}
}

// Get returns the current snapshot and whether it exists
func (c *Cache) Get() (*SystemSnapshot, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.snapshot == nil {
		return nil, false
	}
	return c.snapshot, true
}

// Set updates the cached snapshot
func (c *Cache) Set(snapshot *SystemSnapshot) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.snapshot = snapshot
	c.updatedAt = time.Now()
}

// UpdatedAt returns when the cache was last updated
func (c *Cache) UpdatedAt() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.updatedAt
}

// WaitForUpdate blocks until the cache is updated after the given timestamp
// Returns the new snapshot and true, or nil and false if timeout is reached
func (c *Cache) WaitForUpdate(after time.Time, timeout time.Duration) (*SystemSnapshot, bool) {
	c.mu.Lock()
	// Check if we have a newer snapshot already
	if !c.updatedAt.IsZero() && c.updatedAt.After(after) {
		snapshot := c.snapshot
		c.mu.Unlock()
		return snapshot, true
	}

	// Create condition variable for signaling updates
	_ = sync.NewCond(&c.mu)

	// Use a goroutine to signal when update happens
	done := make(chan struct{})
	go func() {
		for {
			c.mu.Lock()
			if !c.updatedAt.IsZero() && c.updatedAt.After(after) {
				close(done)
				c.mu.Unlock()
				return
			}
			c.mu.Unlock()
			time.Sleep(100 * time.Millisecond)
		}
	}()

	// Wait for signal or timeout
	var snapshot *SystemSnapshot
	snapshot, ok := func() (*SystemSnapshot, bool) {
		timeoutChan := time.After(timeout)
		select {
		case <-done:
			c.mu.Lock()
			snapshot = c.snapshot
			ok := snapshot != nil
			c.mu.Unlock()
			return snapshot, ok
		case <-timeoutChan:
			return nil, false
		}
	}()

	return snapshot, ok
}
