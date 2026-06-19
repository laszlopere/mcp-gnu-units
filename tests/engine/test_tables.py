"""P5 — piecewise-linear table units (TODO §2.4.8, grammar §3.5)."""

import pytest

from mcp_gnu_units.engine import Database, LoadConfig
from mcp_gnu_units.engine.errors import DomainError


@pytest.fixture(scope="session")
def db(symbols):
    return Database(symbols, LoadConfig())


def test_gasmark_exact_tabulated_point(db):
    # Gas mark 4 is tabulated as 809.67 degR; degF (interval) shares the degR size.
    assert db.convert("gasmark(4)", "degF").value.as_float() == pytest.approx(809.67)


def test_gasmark_linear_interpolation(db):
    # Halfway between gas mark 4 (809.67) and 5 (834.67) -> 822.17.
    assert db.convert("gasmark(4.5)", "degF").value.as_float() == pytest.approx(822.17)


def test_table_inverse_interpolation(db):
    # tempF(375) lands exactly on gas mark 5.
    assert db.convert("tempF(375)", "gasmark").value.as_float() == pytest.approx(5.0)


def test_table_out_of_range_raises(db):
    with pytest.raises(DomainError):
        db.convert("gasmark(99)", "degF")


def test_brix_table(db):
    # Brix table maps sugar percentage to density; 20 Brix ≈ 1.08 g/cm^3.
    assert db.convert("brix(20)", "g/cm^3").value.as_float() == pytest.approx(1.0799, rel=1e-4)
