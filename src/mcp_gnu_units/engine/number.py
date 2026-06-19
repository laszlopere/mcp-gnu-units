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

"""The numeric value type for the engine (TODO §2.4.8 / numerics §2.1.6).

``Number`` carries a value that is EXACT (``fractions.Fraction``) wherever the
data allows and INEXACT (``float``) only once an irrational operation forces it.
Every database literal — ``2.54``, ``6.62607015e-34``, the fraction ``1|2`` —
parses losslessly via ``decimal.Decimal`` into a ``Fraction``, so the bulk of the
GNU units database stays rational and our reductions agree with the binary
bit-for-bit. ``float`` (and ``exact=False``) enters only through ``sqrt`` of a
non-perfect square, fractional roots, logs, exponentials, and trig.

The invariant: ``exact is True`` ⇒ ``value`` is a ``Fraction``; ``exact is
False`` ⇒ ``value`` is a ``float``. A binary result is exact iff BOTH operands
are exact. We carry only this boolean now; the full rounded-to-N-decimals verdict
(à la mcp-abacus ``value.py``, a read-only reference we re-implement, never
import) is deferred to the numerics TODO §2.1.6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction


@dataclass(frozen=True)
class Number:
    """An exact rational or an inexact float, tagged with its exactness."""

    value: Fraction | float
    exact: bool

    def __post_init__(self) -> None:
        # Normalize the invariant: exact ⇒ Fraction, inexact ⇒ float.
        if self.exact and not isinstance(self.value, Fraction):
            object.__setattr__(self, "value", Fraction(self.value))
        if not self.exact and not isinstance(self.value, float):
            object.__setattr__(self, "value", float(self.value))

    # -- construction ----------------------------------------------------

    @classmethod
    def exact_int(cls, n: int) -> Number:
        return cls(Fraction(n), True)

    @classmethod
    def from_literal(cls, lexeme: str) -> Number:
        """Parse a single numeric literal (no ``|`` fraction) exactly.

        Handles integers, decimals (incl. a leading ``.``), and scientific
        notation, all via ``Decimal`` so nothing is lost to binary float.
        """
        try:
            return cls(Fraction(Decimal(lexeme)), True)
        except (ArithmeticError, ValueError) as exc:  # pragma: no cover - lexer guards shape
            raise ValueError(f"not a numeric literal: {lexeme!r}") from exc

    # -- helpers ---------------------------------------------------------

    def as_float(self) -> float:
        return float(self.value)

    def is_dimensionless_integer(self) -> bool:
        return self.exact and isinstance(self.value, Fraction) and self.value.denominator == 1

    # -- arithmetic ------------------------------------------------------

    def __neg__(self) -> Number:
        return Number(-self.value, self.exact)

    def __add__(self, other: Number) -> Number:
        if self.exact and other.exact:
            return Number(self.value + other.value, True)
        return Number(self.as_float() + other.as_float(), False)

    def __sub__(self, other: Number) -> Number:
        if self.exact and other.exact:
            return Number(self.value - other.value, True)
        return Number(self.as_float() - other.as_float(), False)

    def __mul__(self, other: Number) -> Number:
        if self.exact and other.exact:
            return Number(self.value * other.value, True)
        return Number(self.as_float() * other.as_float(), False)

    def __truediv__(self, other: Number) -> Number:
        if other.exact and other.value == 0:
            raise ZeroDivisionError("division by zero in unit expression")
        if self.exact and other.exact:
            return Number(self.value / other.value, True)
        return Number(self.as_float() / other.as_float(), False)

    def pow_frac(self, exp: Number) -> Number:
        """Raise to a (dimensionless, pure-number) exponent.

        Exact when the exponent is an exact integer, or an exact rational whose
        root is exact (a perfect power). Otherwise inexact float.
        """
        # Integer exponent: stays exact for an exact base.
        if exp.is_dimensionless_integer():
            n = int(exp.value)
            if self.exact:
                # Fraction ** int is exact (negative n inverts).
                return Number(self.value**n, True)
            return Number(self.as_float() ** n, False)

        # Rational exponent on an exact base: try for an exact root.
        if self.exact and exp.exact and isinstance(exp.value, Fraction):
            rooted = _exact_rational_pow(self.value, exp.value)  # type: ignore[arg-type]
            if rooted is not None:
                return Number(rooted, True)

        base = self.as_float()
        e = exp.as_float()
        if base < 0:
            raise ValueError("fractional power of a negative number is not real")
        return Number(base**e, False)


# -- exact roots ---------------------------------------------------------------


def _iroot(n: int, k: int) -> int | None:
    """Exact integer k-th root of n ≥ 0, or None if not a perfect k-th power."""
    if n < 0:
        return None
    if n in (0, 1):
        return n
    guess = round(n ** (1.0 / k))
    for cand in range(max(0, guess - 2), guess + 3):
        if cand**k == n:
            return cand
    return None


def _exact_rational_pow(value: Fraction, exp: Fraction) -> Fraction | None:
    """value ** exp as an exact Fraction, or None if the root is irrational."""
    p, q = exp.numerator, exp.denominator  # q > 0 by Fraction invariant
    powered = value**p  # Fraction; p may be negative
    neg = powered < 0
    num = abs(powered.numerator)
    den = powered.denominator
    rn = _iroot(num, q)
    rd = _iroot(den, q)
    if rn is None or rd is None:
        return None
    result = Fraction(rn, rd)
    if neg:
        if q % 2 == 0:
            return None  # even root of a negative — not real
        result = -result
    return result


# -- irrational unary functions (always inexact) -------------------------------


def _inexact(fn, x: Number) -> Number:
    return Number(fn(x.as_float()), False)


def sqrt(x: Number) -> Number:
    if x.exact:
        rooted = _exact_rational_pow(x.value, Fraction(1, 2))  # type: ignore[arg-type]
        if rooted is not None:
            return Number(rooted, True)
    if x.as_float() < 0:
        raise ValueError("sqrt of a negative number is not real")
    return _inexact(math.sqrt, x)


def cuberoot(x: Number) -> Number:
    if x.exact:
        rooted = _exact_rational_pow(x.value, Fraction(1, 3))  # type: ignore[arg-type]
        if rooted is not None:
            return Number(rooted, True)
    return Number(math.copysign(abs(x.as_float()) ** (1.0 / 3.0), x.as_float()), False)


def ln(x: Number) -> Number:
    return _inexact(math.log, x)


def log(x: Number) -> Number:
    return _inexact(math.log10, x)


def log2(x: Number) -> Number:
    return _inexact(math.log2, x)


def exp(x: Number) -> Number:
    return _inexact(math.exp, x)


def sin(x: Number) -> Number:
    return _inexact(math.sin, x)


def cos(x: Number) -> Number:
    return _inexact(math.cos, x)


def tan(x: Number) -> Number:
    return _inexact(math.tan, x)


def asin(x: Number) -> Number:
    return _inexact(math.asin, x)


def acos(x: Number) -> Number:
    return _inexact(math.acos, x)


def atan(x: Number) -> Number:
    return _inexact(math.atan, x)
