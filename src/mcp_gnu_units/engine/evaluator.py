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

"""Reduce an expression AST to a :class:`Quantity` (TODO §2.4.8).

Name resolution tries a direct unit first, then greedy longest-prefix matching
(``kilometer`` → ``kilo`` × ``meter``), recursively. Unit reductions are memoized
because only the handful of units in a query are ever reduced — not the whole
database. Nonlinear function units (``tempC(x)``) evaluate their forward closure
with the parameters bound in a local environment; ``~f(arg)`` applies the inverse
closure (the inverse expression references the function's own name).
"""

from __future__ import annotations

from .ast import BinOp, Expr, FuncCall, Inverse, Juxt, Neg, Num, Power, UnitRef
from .builtins import BUILTINS
from .dimension import DIMENSIONLESS, Dimension
from .errors import (
    DomainError,
    NotConformableError,
    ParseError,
    RangeError,
    UndefinedUnitError,
    UnitsError,
)
from .functions import FunctionUnit
from .number import Number
from .quantity import Quantity
from .symbols import DerivedUnit, PrimitiveUnit, SymbolTable
from .tables import PiecewiseTable, interpolate_forward, interpolate_inverse

_Env = dict[str, Quantity]


def _plural_candidates(name: str) -> list[str]:
    """Singular forms to try for a plural unit name: ``days`` → ``day``,
    ``inches`` → ``inch``. GNU units strips a trailing ``s`` or ``es``."""
    cands: list[str] = []
    if len(name) > 1 and name.endswith("s"):
        cands.append(name[:-1])
    if len(name) > 2 and name.endswith("es"):
        cands.append(name[:-2])
    return cands


class Evaluator:
    """Stateful reducer bound to one symbol table (caches unit reductions)."""

    def __init__(self, symbols: SymbolTable) -> None:
        self._symbols = symbols
        self._cache: dict[str, Quantity] = {}
        self._resolving: set[str] = set()

    # -- expression walk -------------------------------------------------

    def reduce_expr(self, expr: Expr, env: _Env | None = None) -> Quantity:
        if isinstance(expr, Num):
            return Quantity(expr.value, DIMENSIONLESS)
        if isinstance(expr, UnitRef):
            return self._reduce_name(expr.name, env)
        if isinstance(expr, Juxt):
            return self.reduce_expr(expr.left, env) * self.reduce_expr(expr.right, env)
        if isinstance(expr, BinOp):
            return self._binop(expr, env)
        if isinstance(expr, Power):
            base = self.reduce_expr(expr.base, env)
            exponent = self.reduce_expr(expr.exponent, env)
            return base.pow(exponent)
        if isinstance(expr, Neg):
            return -self.reduce_expr(expr.operand, env)
        if isinstance(expr, FuncCall):
            return self._call(expr, env)
        if isinstance(expr, Inverse):
            return self._apply_inverse(expr, env)
        raise ParseError(f"cannot evaluate node {type(expr).__name__}")  # pragma: no cover

    def _binop(self, expr: BinOp, env: _Env | None) -> Quantity:
        left = self.reduce_expr(expr.left, env)
        right = self.reduce_expr(expr.right, env)
        if expr.op == "*":
            return left * right
        if expr.op == "/":
            return left / right
        if expr.op == "+":
            return left + right
        return left - right

    # -- name / prefix resolution ---------------------------------------

    def _reduce_name(self, name: str, env: _Env | None) -> Quantity:
        if env is not None and name in env:
            return env[name]
        if name in self._cache:
            return self._cache[name]
        quantity = self._resolve(name)
        self._cache[name] = quantity
        return quantity

    def _resolve(self, name: str) -> Quantity:
        unit = self._symbols.units.get(name)
        if unit is not None:
            return self._reduce_unit(name, unit)
        # A bare prefix name resolves to its multiplier (units: `kilo` == 1000).
        # This also lets prefixes defined via another prefix work (`k-  kilo`).
        prefix = self._symbols.prefixes.get(name)
        if prefix is not None:
            return self.reduce_expr(prefix.expr)
        # A single prefix on a DIRECT unit ('us' = micro·s). The remainder must be
        # a plain unit — no stacking — which is what rules out 'days' = da·(y·s).
        prefixed = self._resolve_prefixed(name)
        if prefixed is not None:
            return prefixed
        # Only then strip a plural and recurse: 'days' → day, 'inches' → inch,
        # 'kilometers' → kilometer → kilo·meter.
        for candidate in _plural_candidates(name):
            try:
                return self._reduce_name(candidate, None)
            except UndefinedUnitError:
                continue
        raise UndefinedUnitError(f"'{name}' is not a defined unit")

    def _reduce_unit(self, name: str, unit: PrimitiveUnit | DerivedUnit) -> Quantity:
        if isinstance(unit, PrimitiveUnit):
            dim = DIMENSIONLESS if unit.dimensionless else Dimension.base(name)
            return Quantity(Number.exact_int(1), dim)
        if name in self._resolving:
            raise UndefinedUnitError(f"circular definition for '{name}'")
        self._resolving.add(name)
        try:
            return self.reduce_expr(unit.expr)
        finally:
            self._resolving.discard(name)

    def _resolve_prefixed(self, name: str) -> Quantity | None:
        """Greedy longest-prefix match onto a DIRECT unit: kilo+meter, micro+s.

        The remainder must be a plain unit (no second prefix, no plural), so that
        ``days`` does NOT decompose to ``da``·``ys`` — it has no such split and
        falls through to plural handling instead.
        """
        for prefix in self._symbols.prefixes_by_length():
            if len(prefix) < len(name) and name.startswith(prefix):
                remainder = name[len(prefix) :]
                unit = self._symbols.units.get(remainder)
                if unit is None:
                    continue
                pref = self.reduce_expr(self._symbols.prefixes[prefix].expr)
                return pref * self._reduce_unit(remainder, unit)
        return None

    # -- functions -------------------------------------------------------

    def _call(self, expr: FuncCall, env: _Env | None) -> Quantity:
        name = expr.name
        builtin = BUILTINS.get(name)
        if builtin is not None:
            if len(expr.args) != 1:
                raise ParseError(f"{name}() takes one argument")
            return builtin(self.reduce_expr(expr.args[0], env))
        func = self._resolve_function(name)
        if isinstance(func, FunctionUnit):
            args = [self.reduce_expr(a, env) for a in expr.args]
            return self.apply_forward(func, args)
        table = self._symbols.tables.get(name)
        if isinstance(table, PiecewiseTable):
            if len(expr.args) != 1:
                raise ParseError(f"{name}() takes one argument")
            return self.apply_table_forward(table, self.reduce_expr(expr.args[0], env))
        raise UndefinedUnitError(f"'{name}' is not a defined function")

    # -- tables ----------------------------------------------------------

    def apply_table_forward(self, table: PiecewiseTable, arg: Quantity) -> Quantity:
        if not arg.is_dimensionless:
            raise NotConformableError(
                f"{table.name}() takes a dimensionless argument",
                have=str(arg.dimension),
                want="1",
            )
        value = interpolate_forward(table, arg.coefficient)
        return Quantity(value, DIMENSIONLESS) * self.reduce_expr(table.out_unit)

    def apply_table_inverse(self, table: PiecewiseTable, value: Quantity) -> Quantity:
        out = self.reduce_expr(table.out_unit)
        if value.dimension != out.dimension:
            raise NotConformableError(
                f"cannot convert to table {table.name!r}",
                have=str(value.dimension),
                want=str(out.dimension),
            )
        magnitude = value.coefficient / out.coefficient
        return Quantity(interpolate_inverse(table, magnitude), DIMENSIONLESS)

    def _resolve_function(self, name: str) -> FunctionUnit | None:
        """Follow zero-argument aliases: ``dB() decibel`` → ``decibel`` (§3.4)."""
        func = self._symbols.functions.get(name)
        seen: set[str] = set()
        while (
            isinstance(func, FunctionUnit)
            and not func.params
            and isinstance(func.forward, UnitRef)
            and func.forward.name not in seen
        ):
            seen.add(func.forward.name)
            target = self._symbols.functions.get(func.forward.name)
            if not isinstance(target, FunctionUnit):
                break
            func = target
        return func if isinstance(func, FunctionUnit) else None

    def apply_forward(self, func: FunctionUnit, args: list[Quantity]) -> Quantity:
        if len(args) != len(func.params):
            raise ParseError(
                f"{func.name}() expects {len(func.params)} argument(s), got {len(args)}"
            )
        if func.domain and not func.noerror:
            # domain may declare fewer intervals than params; pair the leading ones.
            for interval, arg in zip(func.domain, args, strict=False):
                if not interval.contains(arg.coefficient):
                    raise DomainError(f"argument to {func.name}() is outside its domain")
        env = dict(zip(func.params, args, strict=True))
        result = self.reduce_expr(func.forward, env)
        if func.range and not func.noerror:
            if not func.range[0].contains(result.coefficient):
                raise RangeError(f"result of {func.name}() is outside its range")
        return result

    def apply_inverse(self, func: FunctionUnit, value: Quantity) -> Quantity:
        if func.inverse is None:
            raise UnitsError(f"{func.name}() has no inverse")
        return self.reduce_expr(func.inverse, {func.name: value})

    def _apply_inverse(self, expr: Inverse, env: _Env | None) -> Quantity:
        target = expr.operand
        if not isinstance(target, FuncCall):
            raise ParseError("'~' must be applied to a function call")
        func = self._resolve_function(target.name)
        if not isinstance(func, FunctionUnit):
            raise UndefinedUnitError(f"'{target.name}' is not a defined function")
        if len(target.args) != 1:
            raise ParseError(f"~{target.name}() takes one argument")
        value = self.reduce_expr(target.args[0], env)
        return self.apply_inverse(func, value)
