# Contributing

Thanks for helping improve `h1b-sponsor-mcp`. The project goal is simple:
give MCP clients a safe, read-only way to query public H-1B employer data with
clear caveats and reproducible numbers.

Repository: https://github.com/ujjwalredd/H1B-Sponsor-MCP.git

## Ground Rules

- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Keep the server read-only unless there is a deliberate design discussion
  first.
- Do not add network listeners, shell execution, dynamic code execution, SQL
  string construction, or pickle loading.
- Treat all user-provided MCP arguments as hostile until validated.
- Do not include secrets, private credentials, or private immigration records
  in issues, tests, fixtures, or commits.
- Make data caveats explicit. This project should not imply legal or
  immigration advice.

## Local Setup

```bash
git clone https://github.com/ujjwalredd/H1B-Sponsor-MCP.git
cd H1B-Sponsor-MCP
python -m pip install -e ".[dev]"
```

Run checks:

```bash
pytest
ruff check src tests
```

If you want to run tests without installing the editable package:

```bash
PYTHONPATH=src pytest
```

## Development Notes

- MCP tool functions live in `src/h1b_mcp/server.py`.
- Data loading and pandas queries live in `src/h1b_mcp/data.py`.
- Input validation and allowlists live in `src/h1b_mcp/validation.py`.
- Tests live in `tests/`.
- The bundled dataset lives at
  `src/h1b_mcp/data/h1b_employers_clean.parquet`.

Keep validation close to the MCP boundary. New tool arguments should be
validated before they reach the data layer.

## Pull Request Checklist

Before opening a pull request:

- Add or update tests for changed behavior.
- Run `pytest`.
- Run `ruff check src tests`.
- Update README or DATA.md if tools, install steps, caveats, or dataset counts
  change.
- Update SECURITY.md if the server surface, transport, or threat model changes.
- Keep generated artifacts out of the diff unless they are intentionally part
  of the release.

## Reporting Security Issues

Do not open public issues for vulnerabilities. Use the process in
[SECURITY.md](SECURITY.md).
