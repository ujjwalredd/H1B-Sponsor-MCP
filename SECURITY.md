# Security Policy

## Supported Versions

Security fixes target the default branch and the latest published release, if a
release has been published. If you maintain a fork or pinned commit, pull the
latest security fixes before deploying.

## Threat Model

This MCP server exposes a read-only, public USCIS dataset over stdio. The main
risks are not data theft from the packaged dataset, but abuse of the tool
surface:

- Malicious or malformed tool arguments from a compromised client.
- Prompt-injected tool arguments routed through an AI assistant.
- Resource exhaustion from oversized queries or result sets.
- Accidental leakage of internal paths or stack traces.

## Defensive Design

### Input Handling

| Risk | Mitigation |
| --- | --- |
| Regex injection via search text | User text is escaped with `re.escape()` before pattern matching. |
| Arbitrary column or expression injection | `state`, `naics_code`, and `metric` are validated against fixed allowlists. |
| Oversized inputs | Queries are capped at 200 characters; limits are capped at 100 rows. |
| Invalid years | Years are bounded to the packaged dataset range, FY2009-FY2026. |
| Type confusion | Validators reject unexpected types, including `bool` where `int` is expected. |

### Query Execution

- No SQL engine and no string-built queries.
- No `eval`, `exec`, pickle loading, or shell execution.
- Data access uses typed pandas filtering and aggregation.
- The dataset is loaded from parquet, treated as read-only, and never written
  back by the server.

### Output Handling

- Result sizes are capped to protect client context windows.
- Outputs are converted to JSON-safe Python values.
- Client-visible errors are sanitized.
- Internal exceptions are logged to stderr, not stdout.

### Transport And Deployment

- Default transport is stdio; this package does not open a network listener.
- stdout is reserved for the MCP protocol; logs go to stderr.
- The data path can be overridden only with the operator-controlled
  `H1B_DATA_PATH` environment variable.
- `H1B_DATA_PATH` must point to a `.parquet` file.

## Privacy

The packaged data is public USCIS employer data. It contains employer names,
locations, petition counts, NAICS sectors, and the tax ID fragment published by
USCIS. The MCP tools do not return tax ID values.

Do not include private immigration records, personal documents, credentials, or
secrets in public issues, pull requests, examples, or test fixtures.

## Reporting A Vulnerability

Please do not open a public issue for a vulnerability.

Use GitHub's private security advisory flow for this repository:

https://github.com/ujjwalredd/H1B-Sponsor-MCP/security/advisories/new

Include:

- Affected version, commit, or install method.
- Steps to reproduce.
- Expected impact.
- Any suggested fix, if known.

We aim to acknowledge valid reports within 72 hours.
