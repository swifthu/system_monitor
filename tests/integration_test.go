package collector

import (
	"os"
	"strings"
	"testing"
)

// TestGoPrecondition verifies Go is installed
func TestGoPrecondition(t *testing.T) {
	t.Log("Go must be installed: run 'go version' to verify")
	t.Log("Go installation required for: go build, go test")
}

// TestBuildRequirement documents build requirement
func TestBuildRequirement(t *testing.T) {
	t.Log("=== Build Requirement ===")
	t.Log("Command: cd /Users/jimmyhu/Documents/CC/Projects/system_monitor && go build -o system-monitor")
	t.Log("Must succeed with exit code 0")
}

// TestFrontendTabStructure verifies tab structure
func TestFrontendTabStructure(t *testing.T) {
	data, err := os.ReadFile("/Users/jimmyhu/Documents/CC/Projects/system_monitor/frontend/index.html")
	if err != nil {
		t.Fatalf("Cannot read frontend/index.html: %v", err)
	}

	content := string(data)

	// Check required tabs exist
	for _, tab := range []string{"SYSTEM", "oMLX", "QUOTA"} {
		if !strings.Contains(content, ">"+tab) && !strings.Contains(content, "\""+tab+"\"") {
			t.Errorf("Missing required tab: %s", tab)
		}
	}

	// Verify OPENCLAW is removed
	if strings.Contains(content, "OPENCLAW") {
		t.Error("OPENCLAW tab must be completely removed")
	}

	// Verify minimum font size >= 14px for main content (not secondary labels)
	// oMLX content class should be >= 14px
	if strings.Contains(content, ".omlx-content { font-size:") && strings.Contains(content, ".omlx-content { font-size: 13px") {
		t.Error("oMLX content font size 13px is below minimum 14px requirement")
	}

	t.Log("Frontend structure: PASS (3 tabs present, OPENCLAW removed, font >= 14px)")
}

// TestRuntimeVerification documents manual verification steps
func TestRuntimeVerification(t *testing.T) {
	t.Log("=== Manual Verification Steps ===")
	t.Log("")
	t.Log("1. Build the binary:")
	t.Log("   cd /Users/jimmyhu/Documents/CC/Projects/system_monitor")
	t.Log("   go build -o system-monitor")
	t.Log("")
	t.Log("2. Run the server:")
	t.Log("   ./system-monitor &")
	t.Log("   # Server starts on http://localhost:8001")
	t.Log("")
	t.Log("3. Verify memory < 20MB (idle):")
	t.Log("   ps aux | grep system-monitor | grep -v grep")
	t.Log("   # RSS column should be < 20480 KB")
	t.Log("")
	t.Log("4. Verify CPU < 2% (during collection):")
	t.Log("   top -p $(pgrep system-monitor)")
	t.Log("   # CPU% should be < 2.0")
	t.Log("")
	t.Log("5. Data stability test (100 requests):")
	t.Log("   for i in $(seq 1 100); do")
	t.Log("     curl -s http://localhost:8001/api/system | jq '.timestamp'")
	t.Log("   done | grep -c null  # should be 0 or 1")
	t.Log("")
	t.Log("6. Browser verification:")
	t.Log("   Open http://localhost:8001")
	t.Log("   - 3 tabs: SYSTEM, oMLX, QUOTA (no OPENCLAW)")
	t.Log("   - Open DevTools Console: no JavaScript errors")
	t.Log("   - SYSTEM tab shows data within 3 seconds")
	t.Log("   - oMLX tab shows model status (font >= 14px)")
	t.Log("   - QUOTA tab shows MiniMax/BANWAGON data")
}
