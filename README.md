# mcp-gnu-units

[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

A pure-Python [Model Context Protocol](https://modelcontextprotocol.io) server,
built on the official MCP SDK (FastMCP), exposing precise, offline unit
conversion and dimensional analysis backed by the GNU units database.

> **Status: skeleton / work in progress.** The server currently exposes an
> `info` availability/version tool plus the first conversion tools (`find_units`,
> `convert`); the remaining domain tools are tracked in [`TODO`](TODO). The final
> searchable description and sponsorship section land at publish time
> (TODO §10.5) — do not treat this README as final.

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

## License

GPL-3.0-or-later. See [LICENSE](LICENSE). The bundled GNU units database is
also GPL-3.0-or-later © Free Software Foundation; see [`NOTICE`](NOTICE).
