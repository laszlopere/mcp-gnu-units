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

## License

GPL-3.0-or-later. See [LICENSE](LICENSE). The bundled GNU units database
(`definitions.units`) is GPL-3.0-or-later © Free Software Foundation; its
provenance and attribution are documented at engine-build time (TODO §2.4).
