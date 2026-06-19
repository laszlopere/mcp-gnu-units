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

"""A reduced quantity: a numeric coefficient times a dimension (TODO §2.4.8).

Every unit expression reduces to a ``Quantity`` — e.g. ``mile`` reduces to
``1609.344 m`` (coefficient ``Number(1609.344)``, dimension ``{m: 1}``).
Multiplication/division/exponentiation combine coefficient and dimension
together; addition/subtraction require conformable (equal-dimension) operands,
matching GNU units. The coefficient keeps its exact/inexact tag throughout.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .dimension import DIMENSIONLESS, Dimension
from .errors import NotConformableError
from .number import Number


@dataclass(frozen=True)
class Quantity:
    """A coefficient (``Number``) scaled by a ``Dimension``."""

    coefficient: Number
    dimension: Dimension

    @property
    def is_dimensionless(self) -> bool:
        return self.dimension.is_dimensionless

    def __mul__(self, other: Quantity) -> Quantity:
        return Quantity(self.coefficient * other.coefficient, self.dimension * other.dimension)

    def __truediv__(self, other: Quantity) -> Quantity:
        return Quantity(self.coefficient / other.coefficient, self.dimension / other.dimension)

    def __neg__(self) -> Quantity:
        return Quantity(-self.coefficient, self.dimension)

    def __add__(self, other: Quantity) -> Quantity:
        self._require_conformable(other, "add")
        return Quantity(self.coefficient + other.coefficient, self.dimension)

    def __sub__(self, other: Quantity) -> Quantity:
        self._require_conformable(other, "subtract")
        return Quantity(self.coefficient - other.coefficient, self.dimension)

    def pow(self, exp: Quantity) -> Quantity:
        """Raise to a dimensionless exponent that reduces to a pure number."""
        if not exp.is_dimensionless:
            raise NotConformableError(
                "exponent must be dimensionless", have=str(exp.dimension), want="1"
            )
        new_coeff = self.coefficient.pow_frac(exp.coefficient)
        if self.is_dimensionless:
            return Quantity(new_coeff, DIMENSIONLESS)
        # A dimensioned base needs an exact rational exponent to scale the
        # dimension vector (you cannot have m^1.4142...).
        e = exp.coefficient
        if not (e.exact and isinstance(e.value, Fraction)):
            raise ValueError("a dimensioned quantity needs a rational exponent")
        return Quantity(new_coeff, self.dimension.pow(e.value))

    def conformable(self, other: Quantity) -> bool:
        return self.dimension == other.dimension

    def _require_conformable(self, other: Quantity, verb: str) -> None:
        if self.dimension != other.dimension:
            raise NotConformableError(
                f"cannot {verb} non-conformable quantities",
                have=str(self.dimension),
                want=str(other.dimension),
            )


ONE = Quantity(Number.exact_int(1), DIMENSIONLESS)
