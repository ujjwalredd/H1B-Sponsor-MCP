# Data Notes

This project packages a cleaned parquet copy of the USCIS H-1B Employer Data
Hub "Employer Information" exports so the MCP server can run without an
external database.

## Source And Attribution

Raw source:

> U.S. Citizenship and Immigration Services (USCIS). H-1B Employer Data Hub,
> Employer Information exports.
> https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub

Use that citation when referencing the underlying dataset. This repository
contains a cleaned derivative parquet created for MCP querying; it is not an
official USCIS release.

This project is independent and is not affiliated with, sponsored by, or
endorsed by USCIS, DHS, or the U.S. Government. The source data comes from a
U.S. federal government publication; U.S. Government works are generally not
copyright-protected in the United States under
[17 U.S.C. Section 105](https://www.law.cornell.edu/uscode/text/17/105). Confirm your
own obligations before redistributing data in other jurisdictions or contexts.

## Packaged Dataset

- File: `src/h1b_mcp/data/h1b_employers_clean.parquet`
- Rows: 1,055,650
- Fiscal years: 2009-2026
- Distinct employer name strings: 392,843
- State/postal codes represented: 61
- NAICS sectors represented: 20

FY2026 is partial and should not be compared to complete fiscal years without
calling that out.

## Interpretation

- Counts are petition approvals and denials, not unique workers.
- Employer names are not entity-resolved. One real-world employer may appear
  under multiple spellings, affiliates, or legal entities.
- `approval_rate` is `total_approvals / total_petitions`, where
  `total_petitions = total_approvals + total_denials`.
- Missing NAICS values are preserved as missing data instead of guessed.
- This dataset is useful for research and discovery, but it is not legal or
  immigration advice.

## Columns

| Column | Meaning |
| --- | --- |
| `fiscal_year` | USCIS fiscal year |
| `employer_name` | Petitioner/employer name |
| `tax_id` | Last four EIN digits as published in the source data |
| `naics_code` | 2-digit NAICS sector code or range such as `31-33` |
| `naics_sector` | NAICS sector label |
| `city` | Employer city |
| `state` | USPS state, territory, or military postal code |
| `zip_code` | 5-digit ZIP code string |
| `*_approval` | Petition approval count for the petition category |
| `*_denial` | Petition denial count for the petition category |
| `total_approvals` | Sum of all approval columns |
| `total_denials` | Sum of all denial columns |
| `total_petitions` | Approvals plus denials |
| `approval_rate` | Approval share of decided petitions |
| `source_file` | Source export filename used during preprocessing |

The MCP tools do not expose `tax_id` in their responses.

## Maintenance Checklist

When refreshing the dataset:

- Preserve leading zeros in `tax_id`, `zip_code`, and NAICS-like codes.
- Keep numeric petition counts as integers.
- Recalculate totals and approval rates after cleaning.
- Re-run the full test suite.
- Update this file and README counts if row counts or coverage change.
