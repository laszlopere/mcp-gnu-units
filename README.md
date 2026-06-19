# mcp-gnu-units

[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

A pure-Python [Model Context Protocol](https://modelcontextprotocol.io) server,
built on the official MCP SDK (FastMCP), exposing precise, offline unit
conversion and dimensional analysis backed by the GNU units database.

> **Status: skeleton / work in progress.** The server currently exposes a single
> `info` availability/version tool; the conversion engine and domain tools are
> tracked in [`TODO`](TODO). The final searchable description, homage to GNU
> units, and sponsorship sections land at publish time (TODO §10.5) — do not
> treat this README as final.

Distribution name: `mcp-gnu-units` · import package: `mcp_gnu_units`.

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
