"""H-1B Sponsor MCP server.

Exposes the cleaned USCIS H-1B Employer dataset (FY2009-FY2026) as MCP tools
so AI assistants can answer questions about which companies sponsor H-1B
visas, with verifiable numbers instead of guesses.

Transport: stdio (default). All logging goes to stderr — stdout is reserved
for the MCP protocol.

Security posture:
- All inputs validated/sanitized in validation.py before any data access.
- No SQL, no eval, no shell: queries are typed pandas operations only.
- User search text is regex-escaped — pattern injection is inert.
- Result sizes are hard-capped (MAX_LIMIT) to protect client context.
- Dataset is read-only; the server never writes to disk.
- Error messages returned to clients are sanitized; stack traces stay
  in server-side logs.
"""
from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from .data import H1BDataStore
from .validation import (
    ValidationError,
    validate_limit,
    validate_naics,
    validate_query,
    validate_sort_metric,
    validate_state,
    validate_year,
)

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("h1b_mcp")

mcp = FastMCP(
    "h1b-sponsors",
    instructions=(
        "Query tools over the USCIS H-1B Employer dataset (FY2009-FY2026). "
        "Use search_employers to find companies by name, employer_profile for "
        "a company's full sponsorship history, top_sponsors for rankings, and "
        "the trend/breakdown tools for aggregate analysis. Always cite the "
        "fiscal year(s) behind any number. FY2026 is partial."
    ),
)

_store = H1BDataStore()


def _guarded(fn, **kwargs):
    """Run a data query with sanitized error handling."""
    try:
        return fn(**kwargs)
    except ValidationError as e:
        return {"error": str(e)}
    except FileNotFoundError as e:
        return {"error": str(e)}
    except Exception:
        logger.exception("internal error in %s", fn.__name__)
        return {"error": "internal server error — query failed"}


@mcp.tool()
def search_employers(query: str, year: int | None = None,
                     state: str | None = None, limit: int = 20) -> dict | list:
    """Search H-1B sponsoring employers by (partial) company name.

    Returns matching employers with their active years, states, and lifetime
    petition totals, sorted by petition volume. Use this first to find the
    exact employer name, then employer_profile for detail.

    Args:
        query: Company name or fragment, e.g. "google" or "tata consultancy".
        year: Optional fiscal year filter (2009-2026).
        state: Optional USPS 2-letter state code, e.g. "CA".
        limit: Max results (default 20, max 100).
    """
    def run(**kw):
        q = validate_query(kw['query'])
        return _store.search_employers(
            q,
            year=validate_year(kw['year']),
            state=validate_state(kw['state']),
            limit=validate_limit(kw['limit']),
        )
    return _guarded(run, query=query, year=year, state=state, limit=limit)


@mcp.tool()
def employer_profile(query: str, limit: int = 20) -> dict:
    """Get the full year-by-year H-1B sponsorship history for an employer.

    Returns up to 5 employers matching the query, each with yearly approval/
    denial counts, approval rates, office locations, and industry sectors.
    Best called with a precise name from search_employers.

    Args:
        query: Company name or fragment.
        limit: Max locations listed per employer (default 20, max 100).
    """
    def run(**kw):
        q = validate_query(kw['query'])
        return _store.employer_profile(q, limit=validate_limit(kw['limit']))
    return _guarded(run, query=query, limit=limit)


@mcp.tool()
def top_sponsors(year: int | None = None, state: str | None = None,
                 naics_code: str | None = None,
                 metric: str = "total_approvals", limit: int = 20) -> dict | list:
    """Rank the top H-1B sponsoring employers.

    Filter by fiscal year, state, and/or industry; rank by a chosen metric.
    approval_rate ranking requires >=10 petitions to avoid tiny-sample noise.

    Args:
        year: Optional fiscal year (2009-2026). Omit for all-time.
        state: Optional USPS 2-letter state code.
        naics_code: Optional 2-digit NAICS sector, e.g. "54" (professional/
            scientific/tech) or "31-33" (manufacturing).
        metric: One of total_approvals, total_denials, total_petitions,
            approval_rate, new_employment_approval, continuation_approval.
        limit: Max results (default 20, max 100).
    """
    def run(**kw):
        return _store.top_sponsors(
            year=validate_year(kw['year']),
            state=validate_state(kw['state']),
            naics_code=validate_naics(kw['naics_code']),
            metric=validate_sort_metric(kw['metric']),
            limit=validate_limit(kw['limit']),
        )
    return _guarded(run, year=year, state=state, naics_code=naics_code,
                    metric=metric, limit=limit)


@mcp.tool()
def yearly_trends(state: str | None = None, naics_code: str | None = None) -> dict | list:
    """H-1B sponsorship totals per fiscal year (2009-2026).

    Returns per-year employer counts, approvals, denials, and approval rates —
    optionally filtered to one state and/or industry. Use for trend questions
    like "how has H-1B sponsorship changed over time".

    Args:
        state: Optional USPS 2-letter state code.
        naics_code: Optional 2-digit NAICS sector code.
    """
    def run(**kw):
        return _store.yearly_trends(
            state=validate_state(kw['state']),
            naics_code=validate_naics(kw['naics_code']),
        )
    return _guarded(run, state=state, naics_code=naics_code)


@mcp.tool()
def industry_breakdown(year: int | None = None, state: str | None = None,
                       limit: int = 25) -> dict | list:
    """H-1B sponsorship totals by NAICS industry sector.

    Which industries sponsor the most H-1B workers. Optionally filter by
    fiscal year and state.

    Args:
        year: Optional fiscal year (2009-2026).
        state: Optional USPS 2-letter state code.
        limit: Max sectors returned (default 25).
    """
    def run(**kw):
        return _store.industry_breakdown(
            year=validate_year(kw['year']),
            state=validate_state(kw['state']),
            limit=validate_limit(kw['limit']),
        )
    return _guarded(run, year=year, state=state, limit=limit)


@mcp.tool()
def state_breakdown(year: int | None = None, naics_code: str | None = None,
                    limit: int = 60) -> dict | list:
    """H-1B sponsorship totals by US state.

    Which states host the most H-1B sponsoring employers. Optionally filter
    by fiscal year and industry.

    Args:
        year: Optional fiscal year (2009-2026).
        naics_code: Optional 2-digit NAICS sector code.
        limit: Max states returned (default 60 = all).
    """
    def run(**kw):
        return _store.state_breakdown(
            year=validate_year(kw['year']),
            naics_code=validate_naics(kw['naics_code']),
            limit=validate_limit(kw['limit']),
        )
    return _guarded(run, year=year, naics_code=naics_code, limit=limit)


@mcp.tool()
def dataset_info() -> dict:
    """Describe the dataset: source, coverage, row counts, and caveats.

    Call this when unsure what the data covers, or to caveat an answer
    (e.g. FY2026 is a partial year).
    """
    return _guarded(_store.dataset_info)


def main() -> None:
    logger.info("starting h1b-sponsors MCP server (stdio)")
    mcp.run()


if __name__ == "__main__":
    main()
