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

"""Pure-Python GNU units engine: parser, evaluator, and conversion (TODO §2.4.8).

The public surface is intentionally small and is what the future §13 MCP tools
(``convert``, ``convert_to_si``, ``find_units``, ``define_unit``,
``list_prefixes``) call. It is populated as the phases land.
"""

from __future__ import annotations

from .convert import ConversionResult, Database, get_database
from .dimension import DIMENSIONLESS, Dimension
from .errors import (
    DomainError,
    NotConformableError,
    ParseError,
    RangeError,
    UndefinedUnitError,
    UnitsError,
)
from .number import Number
from .quantity import Quantity
from .symbols import LoadConfig

__all__ = [
    "DIMENSIONLESS",
    "ConversionResult",
    "Database",
    "Dimension",
    "DomainError",
    "LoadConfig",
    "NotConformableError",
    "Number",
    "ParseError",
    "Quantity",
    "RangeError",
    "UndefinedUnitError",
    "UnitsError",
    "get_database",
]
