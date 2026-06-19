"""P4 — nonlinear function units: temperature, dB, inverse, domain/range (TODO §2.4.8)."""

import pytest

from mcp_gnu_units.engine import Database, LoadConfig
from mcp_gnu_units.engine.errors import DomainError


@pytest.fixture(scope="session")
def db(symbols):
    return Database(symbols, LoadConfig())


def test_zero_celsius_is_32_fahrenheit(db):
    # The named golden: 0 degC -> 32 degF, via the tempC/tempF function units.
    assert db.convert("tempC(0)", "tempF").value.as_float() == 32.0
    assert db.convert("tempC(100)", "tempF").value.as_float() == 212.0


def test_fahrenheit_back_to_celsius_roundtrips(db):
    assert db.convert("tempF(212)", "tempC").value.as_float() == 100.0
    assert db.convert("tempF(98.6)", "tempC").value.as_float() == pytest.approx(37.0)


def test_celsius_to_kelvin_absolute(db):
    assert db.convert("tempC(0)", "K").value.as_float() == pytest.approx(273.15)


def test_domain_violation_raises(db):
    # Below absolute zero: tempC domain is [-273.15, ).
    with pytest.raises(DomainError):
        db.convert("tempC(-300)", "tempF")


def test_decibel_alias_and_inverse(db):
    # dB() is a zero-arg alias for decibel(); 20 dB == 100x power ratio.
    assert db.convert("dB(20)", "1").value.as_float() == pytest.approx(100.0)
    assert db.convert("100", "dB").value.as_float() == pytest.approx(20.0)


def test_tilde_inverse_in_definition(db):
    # spherevolume's diameter form uses '2 ~circum(...)'-style inverse internally;
    # exercise a function whose own evaluation is well-defined.
    r = db.convert("spherevolume(2 m)", "liter")
    # V = 4/3 * pi * r^3 with r = 2 m  ->  ~33510 L
    assert r.value.as_float() == pytest.approx(33510.32, rel=1e-4)


def test_builtin_sqrt_keeps_exactness(db):
    # sqrt of a perfect square stays exact through the engine.
    assert db.reduce("sqrt(4 m^2)").coefficient.value == 2
    assert db.reduce("sqrt(4 m^2)").coefficient.exact
