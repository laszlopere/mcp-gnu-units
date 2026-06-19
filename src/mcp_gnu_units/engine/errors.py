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

"""Exception hierarchy for the units engine (TODO §2.4.8).

Distinct from the top-level ``errors.py`` (which only reshapes MCP argument
ValidationErrors). These exceptions are raised by the parser/evaluator and are
mapped to clean tool-level messages by the future §13 tools. Every engine error
derives from ``UnitsError`` so a caller can catch the whole family at once.
"""

from __future__ import annotations


class UnitsError(Exception):
    """Base class for every error raised by the units engine."""


class ParseError(UnitsError):
    """A unit expression or database line is syntactically malformed."""


class UndefinedUnitError(UnitsError):
    """A referenced unit, prefix, or function is not defined in the database."""


class NotConformableError(UnitsError):
    """Two quantities have different dimensions and cannot be converted/added.

    Mirrors GNU units' "conformability error". Carries the two reduced
    dimensions for diagnostics when available.
    """

    def __init__(self, message: str, *, have: str | None = None, want: str | None = None) -> None:
        super().__init__(message)
        self.have = have
        self.want = want


class DomainError(UnitsError):
    """A nonlinear function/table was called outside its declared ``domain=``."""


class RangeError(UnitsError):
    """A nonlinear function/table produced a value outside its declared ``range=``."""
