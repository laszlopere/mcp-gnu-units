# mcp-gnu-units

[![CI](https://github.com/laszlopere/mcp-gnu-units/actions/workflows/ci.yml/badge.svg)](https://github.com/laszlopere/mcp-gnu-units/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-db61a2.svg)](https://github.com/sponsors/laszlopere)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://img.shields.io/badge/mypy-checked-2a6db2.svg)](https://mypy-lang.org/)
[![Last commit](https://img.shields.io/github/last-commit/laszlopere/mcp-gnu-units.svg)](https://github.com/laszlopere/mcp-gnu-units/commits)

mcp-gnu-units is an MCP server that gives AI agents precise, offline unit
conversion backed by the GNU units database. Convert between 3000+ units of
measurement — length, mass, time, temperature, area, volume, energy, power,
pressure, speed, data and more — evaluate compound unit expressions like `kW*h`
or `acre*ft`, reduce any quantity to its SI base units, search the unit database
by keyword, and look up the exact definition of any unit, prefix, or physical
constant. Deterministic, dimension-aware, and free of the hardcoded per-category
unit tables every other converter ships.

> **Status: work in progress.** Live tools today: `info`, `find_units`,
> `convert`. The remaining domain tools (`convert_to_si`, `define_unit`,
> `list_prefixes`) are tracked in [`TODO`](TODO). The wording above is the
> near-final searchable description but is not yet frozen for publication.

Distribution name: `mcp-gnu-units` · import package: `mcp_gnu_units`.

## Built on GNU units

This project stands on the shoulders of
[GNU units](https://www.gnu.org/software/units/), the units-conversion program
written and maintained by Adrian Mariano for the Free Software Foundation. Its
database is the product of decades of careful curation — thousands of units,
physical constants drawn from CODATA and NIST, and the conversion semantics that
make dimensional analysis trustworthy. This server would not exist without it.

`mcp-gnu-units` bundles that database **verbatim** (see
[Bundled data & provenance](#bundled-data--provenance) below) and pairs it with
an independent, pure-Python conversion engine, so every number it returns traces
straight back to GNU units' own definitions. It is offered in the same spirit
and under the same license (GPL-3.0-or-later). If you find this useful, the
original earns the credit first: <https://www.gnu.org/software/units/>.

## Bundled data & provenance

This server stands on [GNU units](https://www.gnu.org/software/units/), Adrian
Mariano's units-conversion program, by bundling its unit database verbatim at
`src/mcp_gnu_units/data/definitions.units`. The conversion engine here is an
independent implementation; GNU units supplies the data.

- **Source:** GNU units 2.27 ([tarball](https://ftp.gnu.org/gnu/units/units-2.27.tar.gz)),
  `definitions.units` data version 3.26 (2026-02-25).
- **License:** GPL-3.0-or-later © Free Software Foundation — the same license as
  this project, so the two are wholly compatible.
- **Integrity:** the upstream tarball was GPG-verified (good signature from
  Adrian Mariano) before the file was vendored.

Full attribution, version pins, and checksums are recorded in
[`NOTICE`](NOTICE).

## Sponsoring

mcp-gnu-units is free, open-source software developed in my spare time.
Sponsoring keeps this project alive and actively maintained — it funds new
units-engine features, bug fixes, and ongoing support, and it's a direct signal
that the work is worth continuing.

If the project is useful to you, please consider sponsoring it through
**[GitHub Sponsors](https://github.com/sponsors/laszlopere)**. Click the
**Sponsor** button at the top of the repository, or visit the link directly, and
pick a one-time or recurring tier. Every contribution, large or small, is hugely
appreciated and goes straight back into keeping mcp-gnu-units healthy.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE). The bundled GNU units database is
also GPL-3.0-or-later © Free Software Foundation; see [`NOTICE`](NOTICE).
