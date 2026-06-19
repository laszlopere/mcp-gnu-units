"""P0 — exact/inexact numeric core (TODO §2.4.8)."""

from fractions import Fraction

import pytest

from mcp_gnu_units.engine.number import Number, cuberoot, ln, sqrt


def test_literals_parse_exactly():
    assert Number.from_literal("2.54") == Number(Fraction(127, 50), True)
    assert Number.from_literal("1000") == Number(Fraction(1000), True)
    assert Number.from_literal(".0625") == Number(Fraction(1, 16), True)
    planck = Number.from_literal("6.62607015e-34")
    assert planck.exact
    assert planck.value == Fraction(662607015, 10**8 * 10**34)


def test_exact_arithmetic_stays_rational():
    half = Number.from_literal("1") / Number.from_literal("2")
    assert half == Number(Fraction(1, 2), True)
    assert (half + half).value == Fraction(1)
    assert (half * Number.exact_int(3)).value == Fraction(3, 2)


def test_inexactness_is_contagious():
    inexact = sqrt(Number.exact_int(2))
    assert not inexact.exact
    assert not (inexact * Number.exact_int(2)).exact
    # but a fully-exact chain stays exact
    assert (Number.exact_int(2) * Number.exact_int(3)).exact


def test_perfect_roots_stay_exact():
    assert sqrt(Number.exact_int(4)) == Number(Fraction(2), True)
    assert sqrt(Number(Fraction(1, 4), True)) == Number(Fraction(1, 2), True)
    assert cuberoot(Number.exact_int(27)) == Number(Fraction(3), True)
    # non-perfect root falls to inexact float
    assert not sqrt(Number.exact_int(2)).exact


def test_pow_frac_integer_and_rational():
    assert Number.exact_int(2).pow_frac(Number.exact_int(10)) == Number(Fraction(1024), True)
    # negative integer exponent inverts, still exact
    assert Number.exact_int(2).pow_frac(Number.exact_int(-1)) == Number(Fraction(1, 2), True)
    # rational exponent, perfect power
    assert Number.exact_int(8).pow_frac(Number(Fraction(1, 3), True)) == Number(Fraction(2), True)
    # rational exponent, imperfect -> inexact
    assert not Number.exact_int(2).pow_frac(Number(Fraction(1, 2), True)).exact


def test_division_by_zero_raises():
    with pytest.raises(ZeroDivisionError):
        Number.exact_int(1) / Number.exact_int(0)


def test_transcendental_is_inexact():
    assert not ln(Number.exact_int(10)).exact
