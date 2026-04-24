"""Tests for API client."""
import httpx
import pytest
from unittest.mock import Mock, patch, AsyncMock
from api_client import APIClient, parse_snapshot, SystemSnapshot, BASE_URL


class TestParseSnapshot:
    """Tests for parse_snapshot function."""

    def test_parses_valid_data(self):
        """Test parsing a valid snapshot response."""
        data = {
            "cpu": {"percent": 45.5},
            "memory": {"used": 8192, "total": 16384},
            "network": {"rx_rate": 1024.5, "tx_rate": 512.3},
            "battery": {"percent": 85, "time_remaining": 180},
            "gpu": {"power": 25.0, "total": 100.0},
            "temperature": {"cpu": 65.0, "gpu": 70.0},
        }

        result = parse_snapshot(data)

        assert isinstance(result, SystemSnapshot)
        assert result.cpu_percent == 45.5
        assert result.memory_used == 8192
        assert result.memory_total == 16384
        assert result.network_rx == 1024.5
        assert result.network_tx == 512.3
        assert result.battery_percent == 85
        assert result.battery_time_remaining == 180
        assert result.gpu_power == 25.0
        assert result.gpu_total == 100.0
        assert result.temp_cpu == 65.0
        assert result.temp_gpu == 70.0

    def test_handles_missing_fields_with_defaults(self):
        """Test that missing fields use default values."""
        data = {}

        result = parse_snapshot(data)

        assert result.cpu_percent == 0
        assert result.memory_used == 0
        assert result.memory_total == 0
        assert result.network_rx == 0
        assert result.network_tx == 0
        assert result.battery_percent == 0
        assert result.battery_time_remaining is None
        assert result.gpu_power == 0
        assert result.gpu_total == 0
        assert result.temp_cpu == 0
        assert result.temp_gpu == 0

    def test_handles_partial_data(self):
        """Test parsing with some fields present."""
        data = {
            "cpu": {"percent": 30.0},
            "memory": {"used": 4096, "total": 8192},
        }

        result = parse_snapshot(data)

        assert result.cpu_percent == 30.0
        assert result.memory_used == 4096
        assert result.memory_total == 8192
        assert result.network_rx == 0
        assert result.battery_percent == 0
        assert result.temp_cpu == 0

    def test_battery_time_remaining_can_be_none(self):
        """Test battery time_remaining can be null."""
        data = {
            "battery": {"percent": 100, "time_remaining": None},
        }

        result = parse_snapshot(data)

        assert result.battery_percent == 100
        assert result.battery_time_remaining is None


class TestAPIClient:
    """Tests for APIClient class."""

    def test_init_with_default_url(self):
        """Test client initialization with default base URL."""
        client = APIClient()
        assert client.base_url == BASE_URL

    def test_init_with_custom_url(self):
        """Test client initialization with custom base URL."""
        client = APIClient(base_url="http://localhost:9000")
        assert client.base_url == "http://localhost:9000"

    def test_client_has_httpx_client(self):
        """Test that APIClient creates an httpx client."""
        client = APIClient()
        assert hasattr(client, "_client")
        assert isinstance(client._client, httpx.Client)

    @pytest.mark.asyncio
    async def test_get_snapshot_success(self):
        """Test successful snapshot fetch."""
        mock_response = {
            "cpu": {"percent": 50.0},
            "memory": {"used": 8192, "total": 16384},
            "network": {"rx_rate": 100.0, "tx_rate": 50.0},
            "battery": {"percent": 90, "time_remaining": 120},
            "gpu": {"power": 30.0, "total": 80.0},
            "temperature": {"cpu": 60.0, "gpu": 65.0},
        }

        with patch("api_client.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_client.get.return_value = mock_response_obj
            mock_client_class.return_value = mock_client

            client = APIClient()
            result = await client.get_snapshot()

            assert result is not None
            assert result.cpu_percent == 50.0
            assert result.memory_used == 8192

    @pytest.mark.asyncio
    async def test_get_snapshot_returns_none_on_error(self):
        """Test that get_snapshot returns None on exception."""
        with patch("api_client.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.get.side_effect = Exception("Connection failed")
            mock_client_class.return_value = mock_client

            client = APIClient()
            result = await client.get_snapshot()

            assert result is None
