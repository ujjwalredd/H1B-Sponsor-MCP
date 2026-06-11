"""Input validation and sanitization guardrails.

Every tool input passes through these validators before touching the data
layer. The design goals:

- Reject early with clear, safe error messages (no internals leaked).
- Hard caps on result sizes so a single call can't flood the client context.
- Allowlist validation for enumerable fields (state, NAICS, sort keys).
- Regex-injection safety: user search text is escaped before being used
  in any pattern matching.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------
MIN_YEAR = 2009
MAX_YEAR = 2026
MAX_QUERY_LENGTH = 200
MAX_LIMIT = 100
DEFAULT_LIMIT = 20

VALID_STATES = frozenset({
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID',
    'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS',
    'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK',
    'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV',
    'WI', 'WY', 'DC', 'AS', 'GU', 'MP', 'PR', 'VI', 'FM', 'MH', 'PW',
    'AA', 'AE', 'AP',
})

VALID_NAICS = frozenset({
    '11', '21', '22', '23', '31-33', '42', '44-45', '48-49', '51', '52',
    '53', '54', '55', '56', '61', '62', '71', '72', '81', '92',
})

VALID_SORT_METRICS = frozenset({
    'total_approvals', 'total_denials', 'total_petitions', 'approval_rate',
    'new_employment_approval', 'continuation_approval',
})

# Printable characters reasonable in a company-name query. Space only (not
# \s — that would admit newlines/tabs); blocks control chars and other
# unprintables that have no business in a name search.
_QUERY_ALLOWED = re.compile(r"^[\w \.,&'\-\+\(\)/@#!:;\"]*$", re.UNICODE)


class ValidationError(ValueError):
    """Raised for any invalid tool input. Message is safe to show callers."""


def validate_query(query: str) -> str:
    """Validate and normalize a free-text employer search query."""
    if not isinstance(query, str):
        raise ValidationError("query must be a string")
    query = query.strip()
    if not query:
        raise ValidationError("query must not be empty")
    if len(query) > MAX_QUERY_LENGTH:
        raise ValidationError(f"query too long (max {MAX_QUERY_LENGTH} characters)")
    if not _QUERY_ALLOWED.match(query):
        raise ValidationError("query contains unsupported characters")
    return query


def escape_for_regex(text: str) -> str:
    """Escape user text so it is treated literally inside a regex search."""
    return re.escape(text)


def validate_year(year: int | None) -> int | None:
    if year is None:
        return None
    if not isinstance(year, int) or isinstance(year, bool):
        raise ValidationError("year must be an integer")
    if not (MIN_YEAR <= year <= MAX_YEAR):
        raise ValidationError(f"year must be between {MIN_YEAR} and {MAX_YEAR}")
    return year


def validate_state(state: str | None) -> str | None:
    if state is None:
        return None
    if not isinstance(state, str):
        raise ValidationError("state must be a string")
    state = state.strip().upper()
    if state not in VALID_STATES:
        raise ValidationError(f"invalid state code: {state!r} (use USPS 2-letter codes)")
    return state


def validate_naics(naics_code: str | None) -> str | None:
    if naics_code is None:
        return None
    if not isinstance(naics_code, str):
        raise ValidationError("naics_code must be a string")
    naics_code = naics_code.strip()
    if naics_code not in VALID_NAICS:
        raise ValidationError(
            f"invalid naics_code: {naics_code!r} (valid: {', '.join(sorted(VALID_NAICS))})"
        )
    return naics_code


def validate_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValidationError("limit must be an integer")
    if limit < 1:
        raise ValidationError("limit must be at least 1")
    return min(limit, MAX_LIMIT)


def validate_sort_metric(metric: str | None) -> str:
    if metric is None:
        return 'total_approvals'
    if not isinstance(metric, str):
        raise ValidationError("metric must be a string")
    metric = metric.strip().lower()
    if metric not in VALID_SORT_METRICS:
        raise ValidationError(
            f"invalid metric: {metric!r} (valid: {', '.join(sorted(VALID_SORT_METRICS))})"
        )
    return metric
