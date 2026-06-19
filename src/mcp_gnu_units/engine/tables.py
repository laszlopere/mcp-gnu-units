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

"""Piecewise-linear table units (TODO §2.4.8, grammar §3.5).

A definition like ``gasmark[degR]  .0625 634.67  .125 659.67  …`` defines a unit
by linear interpolation between tabulated ``(input, output)`` pairs; the bracket
gives the dimension of the output column. This module parses the head + pairs;
forward/inverse interpolation against the symbol table is driven by the evaluator
(P5).
"""

from __future__ import annotations

from dataclasses import dataclass

from .ast import Expr
from .errors import DomainError, ParseError
from .number import Number
from .parser import parse


@dataclass(frozen=True)
class PiecewiseTable:
    """A table unit: sorted ``(input, output)`` points + the output-column unit."""

    name: str
    out_unit: Expr
    points: tuple[tuple[Number, Number], ...]
    noerror: bool


def parse_table_def(name: str, out_unit_str: str, rest: str) -> PiecewiseTable:
    """Parse ``name[out_unit] [noerror] in1 out1 in2 out2 …``."""
    out_unit = parse(out_unit_str)
    body = rest.strip()
    noerror = False
    if body.startswith("noerror"):
        noerror = True
        body = body[len("noerror") :].strip()

    nums = [Number.from_literal(tok) for tok in body.split()]
    if len(nums) % 2 != 0:
        raise ParseError(f"table {name!r} has an odd number of values")
    points = tuple((nums[i], nums[i + 1]) for i in range(0, len(nums), 2))
    points = tuple(sorted(points, key=lambda p: p[0].as_float()))
    return PiecewiseTable(name=name, out_unit=out_unit, points=points, noerror=noerror)


def _lerp(x: Number, x0: Number, y0: Number, x1: Number, y1: Number) -> Number:
    """Linear interpolation: the value on the line through (x0,y0)-(x1,y1) at x."""
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


def interpolate_forward(table: PiecewiseTable, x: Number) -> Number:
    """Map an input value to its interpolated output (the bracketed unit)."""
    points = table.points
    xf = x.as_float()
    if xf < points[0][0].as_float() or xf > points[-1][0].as_float():
        if not table.noerror:
            raise DomainError(f"{x.as_float()} is outside table {table.name!r}'s input range")
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0.as_float() <= xf <= x1.as_float():
            return _lerp(x, x0, y0, x1, y1)
    # Out of range with noerror: extrapolate along the nearest segment.
    if xf < points[0][0].as_float():
        (x0, y0), (x1, y1) = points[0], points[1]
    else:
        (x0, y0), (x1, y1) = points[-2], points[-1]
    return _lerp(x, x0, y0, x1, y1)


def interpolate_inverse(table: PiecewiseTable, y: Number) -> Number:
    """Map an output value back to its input (inverse interpolation)."""
    points = table.points
    yf = y.as_float()
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        lo, hi = sorted((y0.as_float(), y1.as_float()))
        if lo <= yf <= hi and y0.as_float() != y1.as_float():
            return _lerp(y, y0, x0, y1, x1)
    if not table.noerror:
        raise DomainError(f"{y.as_float()} is outside table {table.name!r}'s output range")
    (x0, y0), (x1, y1) = points[-2], points[-1]
    return _lerp(y, y0, x0, y1, x1)
