"""Integration tests for the data layer against the real dataset."""
import pytest

from h1b_mcp.data import H1BDataStore


@pytest.fixture(scope="module")
def store():
    return H1BDataStore()


class TestSearch:
    def test_finds_known_employer(self, store):
        results = store.search_employers("infosys", limit=5)
        assert results
        assert any("INFOSYS" in r["employer_name"].upper() for r in results)

    def test_regex_injection_is_literal(self, store):
        # ".*" as a literal substring should match nothing (or near nothing),
        # NOT the entire dataset
        results = store.search_employers(".*", limit=100)
        assert len(results) < 100

    def test_limit_respected(self, store):
        results = store.search_employers("inc", limit=3)
        assert len(results) <= 3

    def test_year_filter(self, store):
        results = store.search_employers("google", year=2020, limit=5)
        for r in results:
            assert r["years_active"] == [2020]

    def test_json_safe_output(self, store):
        import json
        results = store.search_employers("microsoft", limit=5)
        json.dumps(results)  # must not raise


class TestProfile:
    def test_profile_structure(self, store):
        out = store.employer_profile("infosys limited")
        assert out["match_count"] >= 1
        p = out["profiles"][0]
        assert {"employer_name", "yearly_history", "lifetime_approvals"} <= set(p)
        years = [y["fiscal_year"] for y in p["yearly_history"]]
        assert years == sorted(years)

    def test_caps_at_five_profiles(self, store):
        out = store.employer_profile("a")
        assert out["match_count"] <= 5


class TestRankings:
    def test_top_sponsors_sorted(self, store):
        results = store.top_sponsors(year=2024, limit=10)
        vals = [r["total_approvals"] for r in results]
        assert vals == sorted(vals, reverse=True)

    def test_approval_rate_needs_volume(self, store):
        results = store.top_sponsors(metric="approval_rate", limit=10)
        for r in results:
            assert r["total_petitions"] >= 10


class TestAggregates:
    def test_yearly_trends_full_coverage(self, store):
        trends = store.yearly_trends()
        years = [t["fiscal_year"] for t in trends]
        assert years == list(range(2009, 2027))

    def test_industry_breakdown(self, store):
        rows = store.industry_breakdown(year=2024)
        assert rows
        assert all(r["naics_code"] for r in rows)

    def test_state_breakdown(self, store):
        rows = store.state_breakdown(year=2024)
        codes = {r["state"] for r in rows}
        assert "CA" in codes

    def test_dataset_info(self, store):
        info = store.dataset_info()
        assert info["fiscal_years"] == "2009-2026"
        assert info["rows"] > 1_000_000
