"""Tests for input validation guardrails."""
import pytest

from h1b_mcp.validation import (
    MAX_LIMIT,
    ValidationError,
    escape_for_regex,
    validate_limit,
    validate_naics,
    validate_query,
    validate_sort_metric,
    validate_state,
    validate_year,
)


class TestValidateQuery:
    def test_normal_query(self):
        assert validate_query("Google LLC") == "Google LLC"

    def test_strips_whitespace(self):
        assert validate_query("  tata  ") == "tata"

    def test_empty_rejected(self):
        with pytest.raises(ValidationError):
            validate_query("")
        with pytest.raises(ValidationError):
            validate_query("   ")

    def test_too_long_rejected(self):
        with pytest.raises(ValidationError):
            validate_query("a" * 201)

    def test_control_chars_rejected(self):
        with pytest.raises(ValidationError):
            validate_query("foo\x00bar")
        with pytest.raises(ValidationError):
            validate_query("foo\nbar")

    def test_non_string_rejected(self):
        with pytest.raises(ValidationError):
            validate_query(123)  # type: ignore[arg-type]

    def test_company_punctuation_allowed(self):
        # Real employer names contain these
        for q in ["AT&T", "O'Reilly", "Smith, Jones & Co.", "ABC (USA) Inc.",
                  "TECH-CORP", "C++ Experts", "a/b services", "x@y consulting"]:
            assert validate_query(q) == q


class TestRegexEscape:
    def test_regex_metachars_inert(self):
        # ".*" must match literally, not as wildcard
        assert escape_for_regex(".*") == r"\.\*"
        assert escape_for_regex("(a|b)+") == r"\(a\|b\)\+"


class TestValidateYear:
    def test_none_passthrough(self):
        assert validate_year(None) is None

    def test_valid_range(self):
        assert validate_year(2009) == 2009
        assert validate_year(2026) == 2026

    def test_out_of_range(self):
        with pytest.raises(ValidationError):
            validate_year(2008)
        with pytest.raises(ValidationError):
            validate_year(2027)

    def test_bool_rejected(self):
        with pytest.raises(ValidationError):
            validate_year(True)  # type: ignore[arg-type]


class TestValidateState:
    def test_normalizes_case(self):
        assert validate_state("ca") == "CA"

    def test_invalid_rejected(self):
        with pytest.raises(ValidationError):
            validate_state("ZZ")
        with pytest.raises(ValidationError):
            validate_state("California")

    def test_none_passthrough(self):
        assert validate_state(None) is None


class TestValidateNaics:
    def test_valid(self):
        assert validate_naics("54") == "54"
        assert validate_naics("31-33") == "31-33"

    def test_invalid_rejected(self):
        with pytest.raises(ValidationError):
            validate_naics("99")
        with pytest.raises(ValidationError):
            validate_naics("54; DROP TABLE")


class TestValidateLimit:
    def test_default(self):
        assert validate_limit(None) == 20

    def test_caps_at_max(self):
        assert validate_limit(10_000) == MAX_LIMIT

    def test_min_one(self):
        with pytest.raises(ValidationError):
            validate_limit(0)
        with pytest.raises(ValidationError):
            validate_limit(-5)


class TestValidateSortMetric:
    def test_default(self):
        assert validate_sort_metric(None) == "total_approvals"

    def test_valid(self):
        assert validate_sort_metric("approval_rate") == "approval_rate"

    def test_arbitrary_column_rejected(self):
        # Prevents sorting by (and thereby probing) unintended columns
        with pytest.raises(ValidationError):
            validate_sort_metric("__class__")
        with pytest.raises(ValidationError):
            validate_sort_metric("tax_id")
