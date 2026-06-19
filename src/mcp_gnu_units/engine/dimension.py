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

"""Dimensions as exponent vectors over the primitive units (TODO §2.4.8).

A ``Dimension`` maps each primitive unit name (``m``, ``kg``, ``s``, …) to its
exponent. Exponents are ``Fraction`` because the database genuinely has
fractional powers (``m^(1|3)``, the CGS ``sqrt_cm``/``sqrt_g`` primitives).
Two quantities are conformable iff their dimensions are equal; a dimensionless
quantity has the empty dimension. Instances are immutable, hashable, and
normalized (zero exponents dropped, entries sorted) so equality is value
equality.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Dimension:
    """An immutable, normalized map {primitive-name -> Fraction exponent}."""

    exps: tuple[tuple[str, Fraction], ...]

    @staticmethod
    def from_map(m: Mapping[str, Fraction]) -> Dimension:
        items = sorted((k, Fraction(v)) for k, v in m.items() if Fraction(v) != 0)
        return Dimension(tuple(items))

    @staticmethod
    def base(name: str) -> Dimension:
        """The dimension of a single primitive unit, exponent 1."""
        return Dimension(((name, Fraction(1)),))

    def as_dict(self) -> dict[str, Fraction]:
        return dict(self.exps)

    @property
    def is_dimensionless(self) -> bool:
        return not self.exps

    def __mul__(self, other: Dimension) -> Dimension:
        acc = self.as_dict()
        for name, exp in other.exps:
            acc[name] = acc.get(name, Fraction(0)) + exp
        return Dimension.from_map(acc)

    def __truediv__(self, other: Dimension) -> Dimension:
        acc = self.as_dict()
        for name, exp in other.exps:
            acc[name] = acc.get(name, Fraction(0)) - exp
        return Dimension.from_map(acc)

    def pow(self, exp: Fraction) -> Dimension:
        if exp == 0:
            return DIMENSIONLESS
        return Dimension(tuple((name, e * exp) for name, e in self.exps))

    def __str__(self) -> str:
        if not self.exps:
            return "1"
        parts = []
        for name, exp in self.exps:
            parts.append(name if exp == 1 else f"{name}^{_fmt_exp(exp)}")
        return " ".join(parts)


def _fmt_exp(exp: Fraction) -> str:
    return str(exp.numerator) if exp.denominator == 1 else f"({exp.numerator}|{exp.denominator})"


DIMENSIONLESS = Dimension(())
