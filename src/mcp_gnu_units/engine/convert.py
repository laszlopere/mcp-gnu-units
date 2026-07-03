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

"""High-level conversion API — the surface the §13 MCP tools call (TODO §2.4.8).

``Database`` wraps a loaded symbol table and an evaluator and offers ``convert``,
``convert_to_si``, ``reduce``, ``find_units``, ``list_prefixes``, and
``describe``. Linear conversions reduce both sides and take the coefficient
ratio; a nonlinear *target* (``… → tempF``) instead applies that unit's inverse
closure to the reduced source. ``get_database`` returns a cached singleton loaded
via ``importlib.resources``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ast import Expr
from .dimension import Dimension
from .errors import NotConformableError
from .evaluator import Evaluator
from .functions import FunctionUnit
from .number import Number
from .parser import parse
from .quantity import Quantity
from .symbols import DerivedUnit, LoadConfig, PrimitiveUnit, SymbolTable
from .tables import PiecewiseTable


@dataclass(frozen=True)
class ConversionResult:
    """The outcome of a conversion or reduction."""

    quantity: Quantity
    formatted: str

    @property
    def value(self) -> Number:
        return self.quantity.coefficient

    @property
    def exact(self) -> bool:
        return self.quantity.coefficient.exact

    @property
    def dimension(self) -> Dimension:
        return self.quantity.dimension

    @property
    def dimension_signature(self) -> str:
        """The base-unit signature (e.g. ``kg m^2 / s^2``); ``1`` when dimensionless."""
        return _format_dimension(self.dimension)


class Database:
    """A loaded units database with conversion/inspection operations."""

    def __init__(self, symbols: SymbolTable, config: LoadConfig) -> None:
        self._symbols = symbols
        self._config = config
        self._eval = Evaluator(symbols)

    @property
    def symbols(self) -> SymbolTable:
        return self._symbols

    # -- core operations -------------------------------------------------

    def reduce(self, expr: str) -> Quantity:
        """Reduce a unit expression to a coefficient × primitive-dimension form."""
        return self._eval.reduce_expr(parse(expr))

    def convert(self, from_expr: str, to_expr: str) -> ConversionResult:
        """Convert ``from_expr`` into units of ``to_expr``.

        Linear when ``to_expr`` is an ordinary unit (ratio of coefficients);
        nonlinear when ``to_expr`` names a function unit (apply its inverse).
        """
        source = self.reduce(from_expr)
        target_fn = self._target_function(to_expr)
        if target_fn is not None:
            result = self._eval.apply_inverse(target_fn, source)
            return ConversionResult(result, format_quantity(result))
        target_table = self._symbols.tables.get(to_expr.strip())
        if isinstance(target_table, PiecewiseTable):
            result = self._eval.apply_table_inverse(target_table, source)
            return ConversionResult(result, format_quantity(result))
        target = self.reduce(to_expr)
        if source.dimension != target.dimension:
            raise NotConformableError(
                f"cannot convert {from_expr!r} to {to_expr!r}: non-conformable",
                have=str(source.dimension),
                want=str(target.dimension),
            )
        ratio = source.coefficient / target.coefficient
        result = Quantity(ratio, _DIMLESS)
        return ConversionResult(result, format_number(ratio))

    def convert_to_si(self, expr: str) -> ConversionResult:
        """Reduce an expression to its SI base-unit (primitive) form."""
        quantity = self.reduce(expr)
        return ConversionResult(quantity, format_quantity(quantity))

    # -- inspection (for §13 find_units / list_prefixes / define_unit) ---

    def find_units(self, query: str, *, limit: int = 50) -> list[tuple[str, str]]:
        """Find units whose name or definition contains ``query`` (case-insensitive)."""
        needle = query.casefold()
        hits: list[tuple[str, str]] = []
        for name, definition in self._symbols.sources.items():
            if name in self._symbols.prefixes or name.endswith("-"):
                continue
            if needle in name.casefold() or needle in definition.casefold():
                hits.append((name, definition))
                if len(hits) >= limit:
                    break
        return hits

    def list_prefixes(self) -> list[tuple[str, str]]:
        """Every prefix and its multiplier, sorted by descending magnitude."""
        out: list[tuple[str, str, float]] = []
        for name in self._symbols.prefixes:
            q = self._eval.reduce_expr(self._symbols.prefixes[name].expr)
            out.append((name, format_number(q.coefficient), q.coefficient.as_float()))
        out.sort(key=lambda item: item[2], reverse=True)
        return [(name, value) for name, value, _ in out]

    def describe(self, name: str) -> dict[str, object]:
        """Show a unit/prefix/function/table definition and its base reduction."""
        info: dict[str, object] = {"name": name}
        source = self._symbols.sources.get(name) or self._symbols.sources.get(name + "-")
        if source is not None:
            info["definition"] = source
        if name in self._symbols.functions:
            info["kind"] = "function"
            fn = self._symbols.functions[name]
            if isinstance(fn, FunctionUnit):
                info["function"] = self._function_info(fn)
        elif name in self._symbols.tables:
            info["kind"] = "table"
        elif name in self._symbols.prefixes:
            info["kind"] = "prefix"
        elif isinstance(self._symbols.units.get(name), PrimitiveUnit):
            info["kind"] = "primitive"
        elif isinstance(self._symbols.units.get(name), DerivedUnit):
            info["kind"] = "unit"
        try:
            reduced = self.reduce(name)
            info["base_value"] = format_quantity(reduced)
            info["dimension"] = _format_dimension(reduced.dimension)
        except Exception:  # noqa: BLE001 - description is best-effort
            pass
        return info

    def _function_info(self, fn: FunctionUnit) -> dict[str, object]:
        """Tier-1 structured view of a function unit: signature + in/out dims (§15.1)."""
        input_dims = [self._reduce_dim(expr) for expr in (fn.units_in or ())]
        output_dim = self._reduce_dim(fn.units_out) if fn.units_out is not None else None
        params = ", ".join(fn.params)
        signature = f"{fn.name}({params}) -> {output_dim or '?'}"
        info: dict[str, object] = {"signature": signature}
        if input_dims:
            info["input_dimensions"] = input_dims
        info["output_dimension"] = output_dim
        return info

    def _reduce_dim(self, expr: Expr) -> str | None:
        """Reduce an expression to its base-unit dimension signature, best-effort."""
        try:
            return _format_dimension(self._eval.reduce_expr(expr).dimension)
        except Exception:  # noqa: BLE001 - best-effort, like describe()
            return None

    # -- helpers ---------------------------------------------------------

    def _target_function(self, to_expr: str) -> FunctionUnit | None:
        """If ``to_expr`` is a bare function-unit name, return it (following aliases)."""
        name = to_expr.strip()
        if name not in self._symbols.functions:
            return None
        return self._eval._resolve_function(name)


# -- module-level singleton ----------------------------------------------------

_DEFAULT_DB: Database | None = None


def get_database(config: LoadConfig | None = None) -> Database:
    """Return a cached :class:`Database` for the default config (or build a fresh one)."""
    global _DEFAULT_DB
    if config is not None:
        from .loader import load

        return Database(load(config), config)
    if _DEFAULT_DB is None:
        from .loader import load

        cfg = LoadConfig()
        _DEFAULT_DB = Database(load(cfg), cfg)
    return _DEFAULT_DB


# -- formatting ----------------------------------------------------------------

_DIMLESS = Dimension(())


def format_number(n: Number) -> str:
    """Render a number: exact integers exactly, otherwise a compact decimal."""
    if n.exact and n.value.denominator == 1:  # type: ignore[union-attr]
        return str(n.value.numerator)  # type: ignore[union-attr]
    return f"{n.as_float():.12g}"


def format_quantity(q: Quantity) -> str:
    """Render a coefficient × dimension GNU-units style, e.g. ``3.6e+06 kg m^2 / s^2``."""
    coeff = format_number(q.coefficient)
    if q.dimension.is_dimensionless:
        return coeff
    return f"{coeff} {_format_dimension(q.dimension)}".rstrip()


def _format_dimension(dim: Dimension) -> str:
    """Group positive exponents as a numerator and negatives after a ``/``."""
    num = [(name, exp) for name, exp in dim.exps if exp > 0]
    den = [(name, -exp) for name, exp in dim.exps if exp < 0]
    num_str = " ".join(_format_factor(name, exp) for name, exp in num) or "1"
    if not den:
        return num_str
    den_str = " ".join(_format_factor(name, exp) for name, exp in den)
    return f"{num_str} / {den_str}"


def _format_factor(name: str, exp: object) -> str:
    from fractions import Fraction

    e = exp  # Fraction
    if e == 1:
        return name
    if isinstance(e, Fraction) and e.denominator != 1:
        return f"{name}^({e.numerator}|{e.denominator})"
    return f"{name}^{e}"
