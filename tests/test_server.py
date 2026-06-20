"""Tests for server tool functions and error paths."""
import pytest

from h1b_mcp import server


class TestGuarded:
    def test_validation_error_returns_dict(self):
        result = server.search_employers(query="")
        assert isinstance(result, dict)
        assert "error" in result

    def test_invalid_year_returns_error(self):
        result = server.search_employers(query="google", year=1999)
        assert isinstance(result, dict)
        assert "error" in result

    def test_invalid_state_returns_error(self):
        result = server.top_sponsors(state="ZZ")
        assert isinstance(result, dict)
        assert "error" in result

    def test_invalid_metric_returns_error(self):
        result = server.top_sponsors(metric="__class__")
        assert isinstance(result, dict)
        assert "error" in result

    def test_invalid_naics_returns_error(self):
        result = server.industry_breakdown(naics_code="99")
        assert isinstance(result, dict)
        assert "error" in result


class TestToolHappyPaths:
    def test_search_returns_list(self):
        result = server.search_employers(query="infosys", limit=5)
        assert isinstance(result, list)

    def test_employer_profile_returns_dict(self):
        result = server.employer_profile(query="infosys limited")
        assert isinstance(result, dict)
        assert "profiles" in result

    def test_top_sponsors_returns_list(self):
        result = server.top_sponsors(year=2024, limit=5)
        assert isinstance(result, list)
        assert len(result) <= 5

    def test_yearly_trends_returns_list(self):
        result = server.yearly_trends()
        assert isinstance(result, list)

    def test_industry_breakdown_returns_list(self):
        result = server.industry_breakdown(year=2024, limit=5)
        assert isinstance(result, list)

    def test_state_breakdown_returns_list(self):
        result = server.state_breakdown(year=2024, limit=5)
        assert isinstance(result, list)

    def test_dataset_info_returns_dict(self):
        result = server.dataset_info()
        assert isinstance(result, dict)
        assert "rows" in result
        assert "error" not in result

    def test_health_check_ok(self):
        result = server.health_check()
        assert isinstance(result, dict)
        assert result["status"] == "ok"
        assert result["dataset_loaded"] is True
        assert result["rows"] > 0


class TestDataStoreErrors:
    def test_missing_file_returns_error(self, tmp_path):
        from h1b_mcp.data import H1BDataStore
        store = H1BDataStore(data_path=tmp_path / "nonexistent.parquet")
        with pytest.raises(FileNotFoundError):
            _ = store.df

    def test_wrong_extension_raises(self, tmp_path):
        bad = tmp_path / "data.csv"
        bad.write_text("a,b\n1,2\n")
        from h1b_mcp.data import H1BDataStore
        store = H1BDataStore(data_path=bad)
        with pytest.raises(ValueError, match="parquet"):
            _ = store.df

    def test_is_ready_false_before_load(self, tmp_path):
        from h1b_mcp.data import H1BDataStore
        store = H1BDataStore(data_path=tmp_path / "nonexistent.parquet")
        assert store.is_ready is False
