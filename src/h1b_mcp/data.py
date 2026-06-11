"""Read-only data access layer for the H-1B employer dataset.

Loads the cleaned USCIS Employer Information parquet once at startup and
serves all queries from an in-memory pandas DataFrame. No SQL engine, no
string-built queries — every filter is a typed pandas operation, which
removes the injection surface entirely.

The DataFrame is treated as immutable after load; all public functions
return plain Python dicts/lists ready for JSON serialization.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import numpy as np
import pandas as pd

from .validation import escape_for_regex

logger = logging.getLogger(__name__)

# Dataset ships inside the package so `uvx h1b-sponsor-mcp` is self-contained.
_DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "data" / "h1b_employers_clean.parquet"

PETITION_COLS = [
    'new_employment_approval', 'new_employment_denial',
    'continuation_approval', 'continuation_denial',
    'change_same_employer_approval', 'change_same_employer_denial',
    'new_concurrent_approval', 'new_concurrent_denial',
    'change_employer_approval', 'change_employer_denial',
    'amended_approval', 'amended_denial',
]


class H1BDataStore:
    """Thread-safe, lazily-loaded, read-only view over the dataset."""

    def __init__(self, data_path: str | os.PathLike | None = None):
        env_path = os.environ.get("H1B_DATA_PATH")
        self._path = Path(data_path or env_path or _DEFAULT_DATA_PATH).resolve()
        self._df: pd.DataFrame | None = None
        self._lock = threading.Lock()

    # -- loading ----------------------------------------------------------
    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            with self._lock:
                if self._df is None:
                    self._df = self._load()
        return self._df

    def _load(self) -> pd.DataFrame:
        if not self._path.is_file():
            raise FileNotFoundError(
                "H-1B dataset not found. Set H1B_DATA_PATH to the cleaned "
                "parquet file (h1b_employers_clean.parquet)."
            )
        if self._path.suffix != ".parquet":
            raise ValueError("H1B_DATA_PATH must point to a .parquet file")
        logger.info("loading dataset from %s", self._path)
        df = pd.read_parquet(self._path)
        # Defensive: drop any unexpected columns, never mutate in place later
        df = df.drop(columns=[c for c in ("source_file",) if c in df.columns])
        logger.info("loaded %d rows, FY%d-FY%d", len(df), df.fiscal_year.min(), df.fiscal_year.max())
        return df

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _records(frame: pd.DataFrame) -> list[dict]:
        """DataFrame -> JSON-safe list of dicts (NaN/NA -> None, numpy -> py)."""
        out = []
        for rec in frame.to_dict(orient="records"):
            clean = {}
            for k, v in rec.items():
                if v is pd.NA or (isinstance(v, float) and np.isnan(v)):
                    clean[k] = None
                elif isinstance(v, (np.integer,)):
                    clean[k] = int(v)
                elif isinstance(v, (np.floating,)):
                    clean[k] = round(float(v), 4)
                else:
                    clean[k] = v
            out.append(clean)
        return out

    def _filtered(self, year: int | None = None, state: str | None = None,
                  naics_code: str | None = None) -> pd.DataFrame:
        df = self.df
        if year is not None:
            df = df[df.fiscal_year == year]
        if state is not None:
            df = df[df.state == state]
        if naics_code is not None:
            df = df[df.naics_code == naics_code]
        return df

    # -- queries ----------------------------------------------------------
    def search_employers(self, query: str, year: int | None = None,
                         state: str | None = None, limit: int = 20) -> list[dict]:
        """Case-insensitive substring search on employer name (regex-escaped)."""
        pattern = escape_for_regex(query)
        df = self._filtered(year=year, state=state)
        df = df[df.employer_name.notna()]
        hits = df[df.employer_name.str.contains(pattern, case=False, regex=True, na=False)]
        # Aggregate per employer so one company = one row
        agg = (hits.groupby('employer_name', as_index=False)
                   .agg(years_active=('fiscal_year', lambda s: sorted(set(int(y) for y in s))),
                        states=('state', lambda s: sorted(set(s.dropna()))),
                        total_approvals=('total_approvals', 'sum'),
                        total_denials=('total_denials', 'sum'),
                        total_petitions=('total_petitions', 'sum'))
                   .sort_values('total_petitions', ascending=False)
                   .head(limit))
        agg['approval_rate'] = (agg.total_approvals / agg.total_petitions.replace(0, np.nan)).round(4)
        return self._records(agg)

    def employer_profile(self, query: str, limit: int = 20) -> dict:
        """Year-by-year sponsorship history for employers matching the query."""
        pattern = escape_for_regex(query)
        df = self.df
        df = df[df.employer_name.notna()]
        hits = df[df.employer_name.str.contains(pattern, case=False, regex=True, na=False)]
        names = hits.employer_name.unique()[:5]  # cap distinct employers per call
        profiles = []
        for name in names:
            sub = hits[hits.employer_name == name]
            yearly = (sub.groupby('fiscal_year', as_index=False)
                         .agg(total_approvals=('total_approvals', 'sum'),
                              total_denials=('total_denials', 'sum'),
                              total_petitions=('total_petitions', 'sum'),
                              new_employment_approvals=('new_employment_approval', 'sum'),
                              continuations=('continuation_approval', 'sum'))
                         .sort_values('fiscal_year'))
            yearly['approval_rate'] = (
                yearly.total_approvals / yearly.total_petitions.replace(0, np.nan)).round(4)
            locations = sub[['city', 'state']].dropna().drop_duplicates().head(limit)
            sectors = sorted(set(sub.naics_sector.dropna()))
            profiles.append({
                'employer_name': name,
                'sectors': sectors,
                'locations': self._records(locations),
                'lifetime_approvals': int(sub.total_approvals.sum()),
                'lifetime_denials': int(sub.total_denials.sum()),
                'yearly_history': self._records(yearly),
            })
        return {'match_count': int(len(names)), 'profiles': profiles}

    def top_sponsors(self, year: int | None = None, state: str | None = None,
                     naics_code: str | None = None, metric: str = 'total_approvals',
                     limit: int = 20) -> list[dict]:
        df = self._filtered(year=year, state=state, naics_code=naics_code)
        df = df[df.employer_name.notna()]
        agg = (df.groupby('employer_name', as_index=False)
                 .agg(total_approvals=('total_approvals', 'sum'),
                      total_denials=('total_denials', 'sum'),
                      total_petitions=('total_petitions', 'sum'),
                      new_employment_approval=('new_employment_approval', 'sum'),
                      continuation_approval=('continuation_approval', 'sum')))
        agg['approval_rate'] = (agg.total_approvals / agg.total_petitions.replace(0, np.nan)).round(4)
        if metric == 'approval_rate':
            # Require meaningful volume so 1/1 = 100% doesn't top the chart
            agg = agg[agg.total_petitions >= 10]
        agg = agg.sort_values(metric, ascending=False).head(limit)
        return self._records(agg)

    def yearly_trends(self, state: str | None = None,
                      naics_code: str | None = None) -> list[dict]:
        df = self._filtered(state=state, naics_code=naics_code)
        agg = (df.groupby('fiscal_year', as_index=False)
                 .agg(employers=('employer_name', 'nunique'),
                      total_approvals=('total_approvals', 'sum'),
                      total_denials=('total_denials', 'sum'),
                      total_petitions=('total_petitions', 'sum'),
                      new_employment_approvals=('new_employment_approval', 'sum'))
                 .sort_values('fiscal_year'))
        agg['approval_rate'] = (agg.total_approvals / agg.total_petitions.replace(0, np.nan)).round(4)
        return self._records(agg)

    def industry_breakdown(self, year: int | None = None,
                           state: str | None = None, limit: int = 25) -> list[dict]:
        df = self._filtered(year=year, state=state)
        df = df[df.naics_code.notna()]
        agg = (df.groupby(['naics_code', 'naics_sector'], as_index=False)
                 .agg(employers=('employer_name', 'nunique'),
                      total_approvals=('total_approvals', 'sum'),
                      total_denials=('total_denials', 'sum'),
                      total_petitions=('total_petitions', 'sum'))
                 .sort_values('total_approvals', ascending=False)
                 .head(limit))
        agg['approval_rate'] = (agg.total_approvals / agg.total_petitions.replace(0, np.nan)).round(4)
        return self._records(agg)

    def state_breakdown(self, year: int | None = None,
                        naics_code: str | None = None, limit: int = 60) -> list[dict]:
        df = self._filtered(year=year, naics_code=naics_code)
        df = df[df.state.notna()]
        agg = (df.groupby('state', as_index=False)
                 .agg(employers=('employer_name', 'nunique'),
                      total_approvals=('total_approvals', 'sum'),
                      total_denials=('total_denials', 'sum'),
                      total_petitions=('total_petitions', 'sum'))
                 .sort_values('total_approvals', ascending=False)
                 .head(limit))
        agg['approval_rate'] = (agg.total_approvals / agg.total_petitions.replace(0, np.nan)).round(4)
        return self._records(agg)

    def dataset_info(self) -> dict:
        df = self.df
        return {
            'source': 'USCIS H-1B Employer Data Hub (Employer Information)',
            'source_url': (
                'https://www.uscis.gov/tools/reports-and-studies/'
                'h-1b-employer-data-hub'
            ),
            'recommended_citation': (
                'U.S. Citizenship and Immigration Services (USCIS). '
                'H-1B Employer Data Hub, Employer Information exports. '
                'https://www.uscis.gov/tools/reports-and-studies/'
                'h-1b-employer-data-hub'
            ),
            'rows': int(len(df)),
            'fiscal_years': f"{int(df.fiscal_year.min())}-{int(df.fiscal_year.max())}",
            'distinct_employers': int(df.employer_name.nunique()),
            'states_covered': int(df.state.nunique()),
            'naics_sectors': int(df.naics_code.nunique()),
            'attribution': (
                'This project packages a cleaned derivative of public USCIS data. '
                'It is not affiliated with, sponsored by, or endorsed by USCIS, '
                'DHS, or the U.S. Government.'
            ),
            'caveats': [
                "FY2026 is a partial year (data still accruing).",
                "Counts are petition approvals/denials, not unique workers.",
                "An employer may appear under multiple name spellings.",
                "Approval rate is approvals / (approvals + denials).",
                "~11% of rows lack a NAICS industry code (mostly older years).",
                "This information is not legal or immigration advice.",
            ],
        }
