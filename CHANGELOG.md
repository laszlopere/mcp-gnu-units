# Changelog

All notable changes to **mcp-gnu-units** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-03

First public release: a feature-complete, offline GNU units MCP server with all
five domain tools plus the `info` health check.

### Added
- **Pure-Python GNU units engine.** An independent parser + evaluator for the
  GNU units definition language: base and derived units, SI and binary prefixes,
  nonlinear units (e.g. `tempC`/`tempF`, `dB`) via forward/inverse functions,
  piecewise tables, and `!`/`!include` directives. Reduces any unit expression to
  its base dimensions and checks conformability internally.
- **Exact-first numerics.** Conversions are computed with `fractions.Fraction`
  where the math is exact and `decimal.Decimal` where it is not, and every result
  is labelled exact vs. inexact — no silently-rounded answer can masquerade as
  precise. Standard library only; no new runtime dependency.
- **Bundled unit database.** Ships the GNU units database verbatim
  (`definitions.units`, data version 3.26, 2026-02-25) inside the wheel, so the
  server is fully offline and deterministic — the shipped data version is pinned
  and can never drift from what is installed. Provenance, checksums, and the GPG
  verdict are recorded in [`NOTICE`](NOTICE).
- **MCP tools:**
  - `info` — availability, package/Python/MCP-SDK versions, and the bundled GNU
    units database version (parsed from the shipped file's own header).
  - `find_units` — case-insensitive substring search over the database by name or
    definition, each hit enriched with its kind, base-unit dimension, and reduced
    base value so an agent can search and triage in one call.
  - `convert` — convert a value or compound unit expression from one unit to
    another (e.g. `1 mi` → `km`, `1 kW*hour` → `J`), returning the magnitude with
    an exact/inexact verdict and a clean error on non-conformable or unknown units.
  - `convert_to_si` — reduce a value or expression to SI base units (e.g.
    `kW*hour` → `3600000 kg m^2 / s^2`), returning the magnitude, base-unit
    signature, and exact/inexact verdict.
  - `define_unit` — look up a single unit, prefix, physical constant, function, or
    table: its definition, kind, dimension, and base reduction.
  - `list_prefixes` — enumerate every SI and binary/IEC prefix with its multiplier,
    sorted by descending magnitude.
- **LLM-mangled-JSON tolerance.** Tool calls survive the broken JSON some LLM
  clients emit: stringified/double-encoded `arguments` (with single quotes,
  trailing commas, or barewords) are repaired in a stdio interposer before the
  SDK's strict validation, and argument-shape errors are reshaped into concise,
  field-naming messages so the model self-corrects in one turn. Unparseable input
  gets an actionable JSON-RPC `-32700` reply. Adds one runtime dependency,
  `json-repair`.
- **Continuous integration.** GitHub Actions runs ruff (lint + format), mypy, and
  the pytest suite across Python 3.10–3.13 on every push and pull request.
