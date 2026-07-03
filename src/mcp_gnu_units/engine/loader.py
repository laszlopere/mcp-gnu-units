# mcp-gnu-units — pure-Python MCP server for GNU units conversion & dimensional analysis.
# Copyright (C) 2026  Laszlo Pere
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Load the bundled units database into a symbol table (TODO §2.4.8 / §3.5).

A single forward pass: read ``definitions.units`` via ``importlib.resources``
(NOT a relative filesystem path), assemble physical lines into logical lines
(``\\`` continuation, ``#`` comments), and dispatch each line to the directive
processor or to a definition parser. Definitions are admitted only when the
directive processor's conditional-block stack is active. Parsing is eager (so
malformed lines surface at load time); reduction to ``Quantity`` is lazy and
lives in the evaluator.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from importlib.resources import files

from .directives import DirectiveProcessor
from .functions import parse_function_def
from .parser import parse
from .symbols import DerivedUnit, LoadConfig, PrefixDef, PrimitiveUnit, SymbolTable
from .tables import parse_table_def

_DATA_PACKAGE = "mcp_gnu_units.data"
_DATA_FILE = "definitions.units"


def read_database_text() -> str:
    """Read the bundled definitions file as text via importlib.resources."""
    return (files(_DATA_PACKAGE) / _DATA_FILE).read_text(encoding="utf-8")


# The bundled definitions.units carries its own version + date in the top comment
# block (`# Version 3.26` / `# Last updated 25 Febuary 2026`). We read them from
# there rather than pinning a constant, so the reported version can never drift
# from the file actually shipped (TODO §2.4.6 / §5.4).
_VERSION_RE = re.compile(r"^#\s*Version\s+(\S+)", re.MULTILINE)
_UPDATED_RE = re.compile(r"^#\s*Last updated\s+(.+?)\s*$", re.MULTILINE)
_MONTHS = {
    m: i
    for i, m in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
        start=1,
    )
}


def database_version(*, text: str | None = None) -> dict[str, str]:
    """Report the bundled GNU units database version, parsed from its header.

    Returns ``source`` ("GNU units") plus, when present in the file header,
    ``data_version`` (e.g. "3.26") and ``data_updated`` (ISO date, e.g.
    "2026-02-25", falling back to the raw header text if it can't be normalized).
    Only the top comment block is scanned, so this stays cheap enough for the
    ``info`` health check to call without loading the whole database.
    """
    source = read_database_text() if text is None else text
    header = source[:4000]  # version + date live in the leading comment block
    result: dict[str, str] = {"source": "GNU units"}
    version_match = _VERSION_RE.search(header)
    if version_match:
        result["data_version"] = version_match.group(1)
    updated_match = _UPDATED_RE.search(header)
    if updated_match:
        raw = updated_match.group(1)
        result["data_updated"] = _iso_date(raw) or raw
    return result


def _iso_date(text: str) -> str | None:
    """Normalize a ``25 Febuary 2026``-style header date to ISO ``2026-02-25``.

    Best-effort: matches the upstream ``day month year`` form (tolerating the
    file's ``Febuary`` typo by keying on the month's first three letters) and
    returns ``None`` on anything it doesn't recognize, so the caller keeps the
    raw string instead.
    """
    parts = text.split()
    if len(parts) != 3:
        return None
    day, month, year = parts
    mon = _MONTHS.get(month[:3].lower())
    if mon is None or not day.isdigit() or not year.isdigit():
        return None
    return f"{int(year):04d}-{mon:02d}-{int(day):02d}"


def load(config: LoadConfig | None = None, *, text: str | None = None) -> SymbolTable:
    """Parse the database into a populated :class:`SymbolTable`."""
    config = config or LoadConfig()
    source = read_database_text() if text is None else text
    symbols = SymbolTable()
    proc = DirectiveProcessor(config, symbols)

    for logical in _logical_lines(source):
        stripped = logical.strip()
        if not stripped:
            continue
        if stripped.startswith("!"):
            proc.handle(stripped[1:].strip())
            continue
        if proc.active:
            _define(symbols, stripped)

    return symbols


def _logical_lines(text: str) -> Iterator[str]:
    """Yield logical lines: comments stripped, ``\\``-continuations joined."""
    buf = ""
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
            continue
        buf += line
        yield buf
        buf = ""
    if buf:
        yield buf


def _strip_comment(raw: str) -> str:
    idx = raw.find("#")
    return raw if idx < 0 else raw[:idx]


def _define(symbols: SymbolTable, line: str) -> None:
    """Classify a definition line and add it to the symbol table."""
    parts = line.split(None, 1)
    name = parts[0]
    rest = parts[1].strip() if len(parts) > 1 else ""

    if "(" in name and name.endswith(")"):
        fname = name[: name.index("(")]
        params = name[name.index("(") + 1 : -1]
        symbols.add_function(fname, parse_function_def(fname, params, rest))
        symbols.sources[fname] = rest
    elif name.endswith("-"):
        symbols.add_prefix(PrefixDef(name[:-1], parse(rest)))
        symbols.sources[name[:-1] + "-"] = rest
    elif "[" in name and name.endswith("]"):
        tname = name[: name.index("[")]
        out_unit = name[name.index("[") + 1 : -1]
        symbols.add_table(tname, parse_table_def(tname, out_unit, rest))
        symbols.sources[tname] = rest
    elif rest.startswith("!"):
        symbols.add_unit(PrimitiveUnit(name, rest.startswith("!dimensionless")))
        symbols.sources[name] = rest
    elif rest:
        symbols.add_unit(DerivedUnit(name, parse(rest)))
        symbols.sources[name] = rest
