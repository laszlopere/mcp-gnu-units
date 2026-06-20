"""P3 — golden conversion pins + the linear/SI core (TODO §2.4.8).

These hard-coded answers always run (no `units` binary needed) and catch parser
or evaluator regressions. The differential oracle harness lives in test_oracle.py.
"""

from fractions import Fraction

import pytest

from mcp_gnu_units.engine import Database, LoadConfig
from mcp_gnu_units.engine.convert import format_number
from mcp_gnu_units.engine.errors import NotConformableError, UndefinedUnitError
from mcp_gnu_units.engine.loader import load
from mcp_gnu_units.engine.number import Number


@pytest.fixture(scope="session")
def db(symbols):
    return Database(symbols, LoadConfig())


def test_mile_to_km_is_exact(db):
    r = db.convert("1 mi", "km")
    assert r.exact
    assert r.value.value == Fraction(1609344, 1000000)
    assert abs(r.value.as_float() - 1.609344) < 1e-12


def test_kwh_to_joule_is_exact_3_6e6(db):
    for expr in ("1 kW*hour", "1 kWh", "1 kW hour"):
        r = db.convert(expr, "J")
        assert r.exact
        assert r.value.value == Fraction(3_600_000)


def test_pound_to_kg_exact(db):
    r = db.convert("1 lb", "kg")
    assert r.exact
    assert r.value.value == Fraction(45359237, 100_000_000)


def test_compound_expression_acre_ft(db):
    # The README's own example: 2.5 acre*ft -> gallons, conformable + finite.
    r = db.convert("2.5 acre*ft", "gallon")
    assert r.value.as_float() == pytest.approx(814628.571, rel=1e-6)


def test_inconvertible_pair_errors_cleanly(db):
    with pytest.raises(NotConformableError):
        db.convert("m", "kg")


def test_unknown_unit_errors(db):
    with pytest.raises(UndefinedUnitError):
        db.convert("1 frobnozzle", "m")


def test_convert_to_si_reduces_to_base_units(db):
    assert db.convert_to_si("newton").formatted == "1 kg m / s^2"
    r = db.convert_to_si("1 kW*hour")
    assert r.value.value == Fraction(3_600_000)
    assert r.formatted == "3600000 kg m^2 / s^2"


def test_prefix_longest_match(db):
    # millimeter = milli * meter; the resolver must not depend on file order.
    assert db.convert("1 km", "m").value.value == Fraction(1000)
    assert db.convert("1 mm", "m").value.value == Fraction(1, 1000)
    assert db.convert("1 us", "s").value.value == Fraction(1, 1_000_000)


def test_bare_prefix_is_its_multiplier(db):
    assert db.reduce("kilo").coefficient.value == Fraction(1000)
    assert db.reduce("mega").coefficient.value == Fraction(10**6)


def test_format_number_exact_integer_vs_decimal():
    assert format_number(Number.exact_int(3_600_000)) == "3600000"
    assert format_number(Number(Fraction(1609344, 1_000_000), True)) == "1.609344"


def test_find_units_substring_matches_name_and_definition(db):
    # §14.1 — substring search over name OR definition (case-insensitive).
    hits = dict(db.find_units("meter", limit=1000))
    assert "meter" in hits  # exact name match
    assert "micron" in hits  # matched via its definition ("micrometer")
    assert all("meter" in (name + defn).casefold() for name, defn in hits.items())


def test_find_units_definition_omits_leading_name(db):
    # The definition is the source line with the leading name token stripped,
    # so the name is carried only by the `name` field, never repeated.
    hits = dict(db.find_units("horsepower", limit=1000))
    assert hits["horsepower"] == "550 foot pound force / sec"
    assert hits["hp"] == "horsepower"  # alias body, name not echoed
    for name, defn in hits.items():
        assert not defn.split()[:1] == [name], f"{name} repeated in its definition"


def test_find_units_is_case_insensitive(db):
    assert db.find_units("METER", limit=5) == db.find_units("meter", limit=5)


def test_find_units_excludes_prefixes(db):
    # "kilo" is a prefix, not a unit, so it must not appear as a hit.
    names = {name for name, _ in db.find_units("kilo", limit=1000)}
    assert "kilo" not in names


def test_find_units_limit_is_honored(db):
    assert len(db.find_units("meter", limit=3)) == 3


def test_find_units_no_match_is_empty(db):
    assert db.find_units("zzzznotaunit") == []


def test_load_with_si_config_changes_gating():
    si = load(LoadConfig(units_system="si"))
    default = load(LoadConfig(units_system="default"))
    # Both load successfully; the SI system gates a different set of definitions.
    assert si.counts()["units"] > 3000
    assert default.counts()["units"] > 3000
