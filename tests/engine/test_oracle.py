"""P6 — differential oracle tests against the real GNU units binary (TODO §2.4.8).

The binary is a DEV/TEST dependency ONLY — never shipped, never called at
runtime. It is pointed at OUR bundled v3.26 database via ``units -f`` so it
behaves as a faithful oracle for the exact data we parse. Every test here is
skipped when the binary is absent, so the suite still passes in a clean CI; the
hard-coded golden pins in test_convert.py / test_nonlinear.py / test_tables.py
carry the load there.

Install the oracle with ``apt install units`` (Debian/Ubuntu).
"""

import shutil
import subprocess
from importlib.resources import files

import pytest

from mcp_gnu_units.engine import Database, LoadConfig
from mcp_gnu_units.engine.convert import _format_dimension
from mcp_gnu_units.engine.symbols import DerivedUnit

pytestmark = pytest.mark.skipif(
    shutil.which("units") is None, reason="GNU units binary not installed (dev/test oracle)"
)

_DB_PATH = str(files("mcp_gnu_units.data") / "definitions.units")

# Primitives the v2.23 binary and our engine both express cleanly.
_SI_PRIMITIVES = {"m", "kg", "s", "A", "K", "mol", "cd", "bit", "radian", "sr"}


@pytest.fixture(scope="session")
def db(symbols):
    return Database(symbols, LoadConfig())


def units_convert(from_expr: str, to_expr: str) -> float | None:
    """Run the oracle for ``from_expr -> to_expr``; None if it cannot answer.

    stderr (the missing-``!include`` warnings for the unbundled currency/crypto/
    element files) is discarded — those don't affect standard conversions.
    """
    proc = subprocess.run(
        ["units", "-f", _DB_PATH, "--terse", from_expr, to_expr],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    line = proc.stdout.strip().splitlines()
    if not line:
        return None
    try:
        return float(line[0])
    except ValueError:
        return None


def _close(a: float, b: float, rel: float = 1e-6) -> bool:
    if a == b:
        return True
    scale = max(abs(a), abs(b))
    return abs(a - b) <= rel * scale if scale else abs(a - b) <= 1e-12


# -- golden pins, this time verified against the live binary --------------------


@pytest.mark.parametrize(
    ("frm", "to", "expected"),
    [
        ("1 mi", "km", 1.609344),
        ("1 kW*hour", "J", 3.6e6),
        ("tempC(0)", "tempF", 32.0),
        ("tempC(100)", "tempF", 212.0),
        ("1 lb", "kg", 0.45359237),
        ("gasmark(4)", "degF", 809.67),
    ],
)
def test_golden_matches_binary(db, frm, to, expected):
    ours = db.convert(frm, to).value.as_float()
    binary = units_convert(frm, to)
    assert binary is not None, f"oracle could not evaluate {frm!r} -> {to!r}"
    assert _close(ours, binary), f"{frm}->{to}: ours={ours} binary={binary}"
    assert _close(ours, expected)


def test_inconvertible_pair_errors_in_both(db):
    from mcp_gnu_units.engine.errors import NotConformableError

    with pytest.raises(NotConformableError):
        db.convert("m", "kg")
    assert units_convert("m", "kg") is None  # binary also refuses


# -- broad differential sweep ---------------------------------------------------


def test_differential_reduction_sweep(db):
    """Reduce a deterministic DB sample to SI and diff each against the binary.

    Units the older v2.23 binary doesn't know (v3.26 additions) are skipped, not
    failed: we only assert agreement where BOTH engines produce a value, and that
    a healthy number of comparisons actually ran.
    """
    names = sorted(n for n, u in db.symbols.units.items() if isinstance(u, DerivedUnit))
    sample = names[:: max(1, len(names) // 200)][:120]

    compared = 0
    mismatches: list[tuple[str, float, float]] = []
    for name in sample:
        try:
            ours = db.convert_to_si(name)
        except Exception:  # noqa: BLE001 - unreducible units are simply skipped
            continue
        dim = ours.dimension
        if dim.is_dimensionless:
            continue
        if any(n not in _SI_PRIMITIVES or e.denominator != 1 for n, e in dim.exps):
            continue
        binary = units_convert(f"1 {name}", _format_dimension(dim))
        if binary is None:
            continue
        compared += 1
        if not _close(ours.value.as_float(), binary):
            mismatches.append((name, ours.value.as_float(), binary))

    assert compared >= 30, f"too few comparable units ({compared}); oracle/setup issue?"
    assert not mismatches, f"{len(mismatches)} mismatches vs oracle: {mismatches[:10]}"
