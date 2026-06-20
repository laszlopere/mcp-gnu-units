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

"""The symbol table: units, prefixes, functions, tables, unitlists (TODO §2.4.8).

A plain container populated in one forward pass by ``loader.py``. The actual
reduction of definitions to ``Quantity`` happens lazily in ``evaluator.py`` (only
the handful of units in a query are ever reduced). Prefix resolution
(longest-match) also lives in the evaluator; here we just keep prefix names
sorted by descending length so that lookup is order-independent of the file.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ast import Expr


@dataclass(frozen=True)
class PrimitiveUnit:
    """An irreducible base unit (``s !``) — its own dimension.

    ``dimensionless`` marks a ``!dimensionless`` primitive (``radian``, ``sr``):
    irreducible as a name but contributing no dimension for conformability.
    """

    name: str
    dimensionless: bool


@dataclass(frozen=True)
class DerivedUnit:
    """An ordinary unit defined by an expression (``minute  60 s``)."""

    name: str
    expr: Expr


@dataclass(frozen=True)
class PrefixDef:
    """A prefix (``kilo-  1000``); ``name`` excludes the trailing ``-``."""

    name: str
    expr: Expr


class SymbolTable:
    """Accumulating store of every definition the loader admits."""

    def __init__(self) -> None:
        self.units: dict[str, PrimitiveUnit | DerivedUnit] = {}
        self.prefixes: dict[str, PrefixDef] = {}
        self.functions: dict[str, object] = {}  # name -> FunctionUnit (engine.functions)
        self.tables: dict[str, object] = {}  # name -> PiecewiseTable (engine.tables)
        self.unitlists: dict[str, list[str]] = {}
        # Definition text per defined name (the source line with the leading
        # name token stripped), for find_units/describe (§13). The name is the
        # dict key, so it is not repeated in the value.
        self.sources: dict[str, str] = {}
        self._prefix_order_dirty = True
        self._prefixes_by_length: list[str] = []

    # -- population ------------------------------------------------------

    def add_unit(self, unit: PrimitiveUnit | DerivedUnit) -> None:
        self.units[unit.name] = unit

    def add_prefix(self, prefix: PrefixDef) -> None:
        self.prefixes[prefix.name] = prefix
        self._prefix_order_dirty = True

    def add_function(self, name: str, func: object) -> None:
        self.functions[name] = func

    def add_table(self, name: str, table: object) -> None:
        self.tables[name] = table

    def add_unitlist(self, name: str, members: list[str]) -> None:
        self.unitlists[name] = members

    # -- lookup ----------------------------------------------------------

    def prefixes_by_length(self) -> list[str]:
        """Prefix names sorted longest-first, for greedy prefix matching."""
        if self._prefix_order_dirty:
            self._prefixes_by_length = sorted(self.prefixes, key=len, reverse=True)
            self._prefix_order_dirty = False
        return self._prefixes_by_length

    def counts(self) -> dict[str, int]:
        primitives = sum(1 for u in self.units.values() if isinstance(u, PrimitiveUnit))
        return {
            "units": len(self.units),
            "primitives": primitives,
            "derived": len(self.units) - primitives,
            "prefixes": len(self.prefixes),
            "functions": len(self.functions),
            "tables": len(self.tables),
            "unitlists": len(self.unitlists),
        }


@dataclass
class LoadConfig:
    """Variable environment that gates conditional directive blocks.

    Defaults mirror the GNU units binary so we load the same definitions it would
    under a plain invocation.
    """

    units_system: str = "default"
    units_english: str = "US"
    locale: str = "en_US"
    utf8: bool = True
    extra: dict[str, str] = field(default_factory=dict)
