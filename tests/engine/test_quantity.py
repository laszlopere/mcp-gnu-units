"""P0 — Dimension + Quantity algebra (TODO §2.4.8)."""

from fractions import Fraction

import pytest

from mcp_gnu_units.engine.dimension import DIMENSIONLESS, Dimension
from mcp_gnu_units.engine.errors import NotConformableError
from mcp_gnu_units.engine.number import Number
from mcp_gnu_units.engine.quantity import Quantity


def _q(coeff, dim=DIMENSIONLESS):
    return Quantity(Number.exact_int(coeff), dim)


def test_dimension_normalizes_and_compares():
    m = Dimension.base("m")
    s = Dimension.base("s")
    speed = m / s
    assert speed.as_dict() == {"m": Fraction(1), "s": Fraction(-1)}
    # m/s * s == m (zero exponent dropped)
    assert (speed * s) == m
    assert m != s
    assert (m / m).is_dimensionless


def test_dimension_fractional_power():
    m = Dimension.base("m")
    assert m.pow(Fraction(1, 3)).as_dict() == {"m": Fraction(1, 3)}
    assert m.pow(Fraction(0)) is DIMENSIONLESS or m.pow(Fraction(0)).is_dimensionless


def test_quantity_mul_div_combines_dims():
    m = Dimension.base("m")
    s = Dimension.base("s")
    dist = Quantity(Number.exact_int(100), m)
    time = Quantity(Number.exact_int(4), s)
    speed = dist / time
    assert speed.coefficient.value == Fraction(25)
    assert speed.dimension == m / s


def test_add_requires_conformable():
    m = Dimension.base("m")
    s = Dimension.base("s")
    total = Quantity(Number.exact_int(1), m) + Quantity(Number.exact_int(2), m)
    assert total.coefficient.value == 3
    with pytest.raises(NotConformableError):
        Quantity(Number.exact_int(1), m) + Quantity(Number.exact_int(2), s)


def test_pow_scales_dimension():
    m = Dimension.base("m")
    area = Quantity(Number.exact_int(3), m).pow(_q(2))
    assert area.dimension == m.pow(Fraction(2))
    assert area.coefficient.value == Fraction(9)


def test_pow_requires_dimensionless_exponent():
    m = Dimension.base("m")
    with pytest.raises(NotConformableError):
        _q(2).pow(Quantity(Number.exact_int(2), m))
