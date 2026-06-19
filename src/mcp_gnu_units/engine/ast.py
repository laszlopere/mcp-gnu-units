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

"""Abstract syntax tree for unit expressions (TODO §2.4.8).

Frozen dataclasses produced by ``parser.py`` and consumed by ``evaluator.py``.
``Juxt`` (multiplication by juxtaposition) is kept distinct from ``BinOp('*')``
so parse-shape tests can prove the juxtaposition-vs-``/`` precedence footgun is
encoded correctly, even though the evaluator treats both as multiplication.
"""

from __future__ import annotations

from dataclasses import dataclass

from .number import Number


@dataclass(frozen=True)
class Num:
    """A numeric literal."""

    value: Number


@dataclass(frozen=True)
class UnitRef:
    """A bare name: a unit, or prefix(es) glued to a unit, resolved at eval time."""

    name: str


@dataclass(frozen=True)
class FuncCall:
    """Application of a named (nonlinear) function: ``tempC(x)``."""

    name: str
    args: tuple[Expr, ...]


@dataclass(frozen=True)
class Neg:
    """Unary negation."""

    operand: Expr


@dataclass(frozen=True)
class Inverse:
    """The ``~`` operator: apply the inverse of the function call to its right."""

    operand: Expr


@dataclass(frozen=True)
class Power:
    """Exponentiation ``base ^ exponent`` (the exponent must reduce to a number)."""

    base: Expr
    exponent: Expr


@dataclass(frozen=True)
class Juxt:
    """Multiplication by juxtaposition (a space) — binds tighter than ``*``/``/``."""

    left: Expr
    right: Expr


@dataclass(frozen=True)
class BinOp:
    """A binary ``+``, ``-``, ``*``, or ``/`` operator."""

    op: str
    left: Expr
    right: Expr


Expr = Num | UnitRef | FuncCall | Neg | Inverse | Power | Juxt | BinOp
