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

"""Built-in math functions the database itself calls (TODO §2.4.8).

GNU units exposes ``sqrt``, ``cuberoot``, and the usual transcendental functions
inside unit definitions (e.g. ``abs(x) noerror sqrt(x^2)``). ``sqrt``/``cuberoot``
operate on a dimensioned quantity (``sqrt(m^2) == m``); the transcendental
functions require a dimensionless argument and yield an inexact dimensionless
result.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction

from . import number
from .dimension import DIMENSIONLESS
from .errors import NotConformableError
from .number import Number
from .quantity import Quantity

_HALF = Quantity(Number(Fraction(1, 2), True), DIMENSIONLESS)
_THIRD = Quantity(Number(Fraction(1, 3), True), DIMENSIONLESS)


def _sqrt(q: Quantity) -> Quantity:
    return q.pow(_HALF)


def _cuberoot(q: Quantity) -> Quantity:
    return q.pow(_THIRD)


def _transcendental(fn: Callable[[Number], Number], name: str) -> Callable[[Quantity], Quantity]:
    def apply(q: Quantity) -> Quantity:
        if not q.is_dimensionless:
            raise NotConformableError(
                f"{name}() requires a dimensionless argument", have=str(q.dimension), want="1"
            )
        return Quantity(fn(q.coefficient), DIMENSIONLESS)

    return apply


BUILTINS: dict[str, Callable[[Quantity], Quantity]] = {
    "sqrt": _sqrt,
    "cuberoot": _cuberoot,
    "ln": _transcendental(number.ln, "ln"),
    "log": _transcendental(number.log, "log"),
    "log2": _transcendental(number.log2, "log2"),
    "exp": _transcendental(number.exp, "exp"),
    "sin": _transcendental(number.sin, "sin"),
    "cos": _transcendental(number.cos, "cos"),
    "tan": _transcendental(number.tan, "tan"),
    "asin": _transcendental(number.asin, "asin"),
    "acos": _transcendental(number.acos, "acos"),
    "atan": _transcendental(number.atan, "atan"),
}
