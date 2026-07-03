"""P2 — load the full bundled database and gate on directives (TODO §2.4.8)."""

from mcp_gnu_units.engine.directives import DirectiveProcessor
from mcp_gnu_units.engine.functions import FunctionUnit
from mcp_gnu_units.engine.loader import _logical_lines, database_version, load
from mcp_gnu_units.engine.symbols import (
    DerivedUnit,
    LoadConfig,
    PrimitiveUnit,
    SymbolTable,
)
from mcp_gnu_units.engine.tables import PiecewiseTable


def test_full_database_loads_without_error(symbols):
    counts = symbols.counts()
    # The bundled v3.26 file has 17 primitive '!' lines, 128 prefixes, 151
    # functions, 30 tables — but conditional blocks (CGS systems, locales) gate
    # some out under the default config. Assert generous, stable lower bounds.
    assert counts["primitives"] >= 10
    assert counts["prefixes"] >= 120
    assert counts["functions"] >= 140
    assert counts["tables"] == 30
    assert counts["units"] > 3000


def test_core_symbols_present(symbols):
    for prim in ("s", "m", "kg", "K", "A", "mol", "cd"):
        assert isinstance(symbols.units[prim], PrimitiveUnit)
    assert isinstance(symbols.units["mile"], DerivedUnit)
    for prefix in ("kilo", "milli", "mega"):
        assert prefix in symbols.prefixes
    assert isinstance(symbols.functions["tempC"], FunctionUnit)
    assert isinstance(symbols.tables["gasmark"], PiecewiseTable)


def test_tempC_function_parsed_with_attrs(symbols):
    fn = symbols.functions["tempC"]
    assert fn.params == ("x",)
    assert fn.inverse is not None  # has a ';'-separated inverse
    assert fn.domain is not None  # domain=[-273.15,)


def test_radian_is_dimensionless_primitive(symbols):
    radian = symbols.units["radian"]
    assert isinstance(radian, PrimitiveUnit) and radian.dimensionless


def test_logical_line_continuation_and_comments():
    text = "foo 60 \\\n   bar  # trailing\n# whole line\nbaz 2\n"
    lines = list(_logical_lines(text))
    assert lines[0].split() == ["foo", "60", "bar"]
    assert lines[-1].split() == ["baz", "2"]


def test_directive_gating_varnot():
    # A definition inside a non-matching !var block is dropped; outside, kept.
    text = "m !\n!var UNITS_SYSTEM cgs\ngated_unit 5 m\n!endvar\nkept_unit 3 m\n"
    st = load(LoadConfig(units_system="default"), text=text)
    assert "gated_unit" not in st.units
    assert "kept_unit" in st.units


def test_directive_processor_active_stack():
    proc = DirectiveProcessor(LoadConfig(units_system="si"), SymbolTable())
    assert proc.active
    proc.handle("var UNITS_SYSTEM si")
    assert proc.active  # matches
    proc.handle("var UNITS_SYSTEM cgs")
    assert not proc.active  # inner does not match
    proc.handle("endvar")
    assert proc.active
    proc.handle("endvar")
    assert proc.active


def test_unitlist_captured():
    text = "hour 3600 s\n!unitlist hms hr;min;sec\n"
    st = load(text=text)
    assert st.unitlists.get("hms") == ["hr", "min", "sec"]


def test_database_version_reads_bundled_header():
    # §2.4.6 — version + date come from the shipped file's own header.
    ver = database_version()
    assert ver["source"] == "GNU units"
    assert ver["data_version"] == "3.26"
    assert ver["data_updated"] == "2026-02-25"


def test_database_version_normalizes_header_date():
    # Tolerates the upstream 'Febuary' typo; ISO-normalizes day/month/year.
    text = "# Version 9.9\n# Last updated 3 Febuary 2030\nm !\n"
    ver = database_version(text=text)
    assert ver["data_version"] == "9.9"
    assert ver["data_updated"] == "2030-02-03"


def test_database_version_keeps_raw_date_when_unparseable():
    text = "# Version 1.0\n# Last updated sometime soon\nm !\n"
    ver = database_version(text=text)
    assert ver["data_version"] == "1.0"
    assert ver["data_updated"] == "sometime soon"
