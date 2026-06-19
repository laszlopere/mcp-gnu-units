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

"""Nonlinear (function) units: ``tempC(x)``, ``tempF(x)``, ``dB`` … (TODO §2.4.8).

A ``FunctionUnit`` is a definition like::

    tempC(x) units=[1;K] domain=[-273.15,) range=[0,) x K + stdtemp ; (tempC+(-stdtemp))/K

This module parses that line into structured data (parameter names, ``units=``
in/out dimension expressions, ``domain=``/``range=`` intervals, the ``noerror``
flag, and the forward + ``;``-separated inverse expression ASTs). Evaluation of
forward/inverse — binding parameters, checking domain/range — is driven by
``evaluator.py`` (P4), which owns the symbol table needed to reduce expressions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .ast import Expr
from .number import Number
from .parser import parse

# An ISO interval must contain a comma ([lo,hi]); requiring it stops a
# parenthesized body expression like "(weight/kg)" from being mis-read as one.
# Intervals may be adjacent with no separator ("domain=(0,)(0,)") or comma-joined
# ("domain=[170,283.15],[3,)"), so the inter-interval separator is optional.
_INTERVAL = r"[\[(][^\])]*,[^\])]*[\])]"
_UNITS_RE = re.compile(r"^units\s*=\s*\[([^\]]*)\]")
_DOMAIN_RE = re.compile(r"^domain\s*=\s*(" + _INTERVAL + r"(?:\s*,?\s*" + _INTERVAL + r")*)")
_RANGE_RE = re.compile(r"^range\s*=\s*(" + _INTERVAL + r"(?:\s*,?\s*" + _INTERVAL + r")*)")
_NOERROR_RE = re.compile(r"^noerror\b")


@dataclass(frozen=True)
class Interval:
    """An ISO half-open interval; a ``None`` endpoint is unbounded."""

    lo: Number | None
    hi: Number | None
    lo_closed: bool
    hi_closed: bool

    def contains(self, x: Number) -> bool:
        xf = x.as_float()
        if self.lo is not None:
            lo = self.lo.as_float()
            if xf < lo or (xf == lo and not self.lo_closed):
                return False
        if self.hi is not None:
            hi = self.hi.as_float()
            if xf > hi or (xf == hi and not self.hi_closed):
                return False
        return True


@dataclass(frozen=True)
class FunctionUnit:
    """A parsed nonlinear unit definition (evaluated by the evaluator)."""

    name: str
    params: tuple[str, ...]
    forward: Expr
    inverse: Expr | None
    units_in: tuple[Expr, ...] | None
    units_out: Expr | None
    domain: tuple[Interval, ...] | None
    range: tuple[Interval, ...] | None
    noerror: bool


def parse_function_def(name: str, params_str: str, rest: str) -> FunctionUnit:
    """Parse a ``name(params) attrs… forward [; inverse]`` definition."""
    params = tuple(p.strip() for p in params_str.split(",") if p.strip())

    units_in: tuple[Expr, ...] | None = None
    units_out: Expr | None = None
    domain: tuple[Interval, ...] | None = None
    rng: tuple[Interval, ...] | None = None
    noerror = False

    body = rest.lstrip()
    while True:
        m = _UNITS_RE.match(body)
        if m:
            units_in, units_out = _parse_units_attr(m.group(1))
            body = body[m.end() :].lstrip()
            continue
        m = _DOMAIN_RE.match(body)
        if m:
            domain = _parse_intervals(m.group(1))
            body = body[m.end() :].lstrip()
            continue
        m = _RANGE_RE.match(body)
        if m:
            rng = _parse_intervals(m.group(1))
            body = body[m.end() :].lstrip()
            continue
        m = _NOERROR_RE.match(body)
        if m:
            noerror = True
            body = body[m.end() :].lstrip()
            continue
        break

    forward_text, sep, inverse_text = body.partition(";")
    forward = parse(forward_text)
    inverse = parse(inverse_text) if sep and inverse_text.strip() else None

    return FunctionUnit(
        name=name,
        params=params,
        forward=forward,
        inverse=inverse,
        units_in=units_in,
        units_out=units_out,
        domain=domain,
        range=rng,
        noerror=noerror,
    )


def _parse_units_attr(text: str) -> tuple[tuple[Expr, ...] | None, Expr | None]:
    """``units=[in;out]`` → (input dim ASTs, output dim AST).

    Single param: ``[1;K]`` → in ``(1,)``, out ``K``. Multi param without an
    output half: ``[K,mph]`` → in ``(K, mph)``, out ``None``.
    """
    in_part, sep, out_part = text.partition(";")
    in_dims = tuple(parse(p) for p in _split_top(in_part) if p.strip())
    out = parse(out_part) if sep and out_part.strip() else None
    return (in_dims or None), out


def _split_top(text: str) -> list[str]:
    return [p for p in text.split(",")]


def _parse_intervals(text: str) -> tuple[Interval, ...]:
    intervals = []
    for raw in re.findall(_INTERVAL, text):
        intervals.append(_parse_interval(raw))
    return tuple(intervals)


def _parse_interval(s: str) -> Interval:
    s = s.strip()
    lo_closed = s[0] == "["
    hi_closed = s[-1] == "]"
    lo_str, _, hi_str = s[1:-1].partition(",")
    return Interval(_const(lo_str), _const(hi_str), lo_closed, hi_closed)


def _const(s: str) -> Number | None:
    """Evaluate a signed decimal/fraction interval endpoint, or None if empty."""
    s = s.strip()
    if not s:
        return None
    sign = 1
    while s and s[0] in "+-":
        if s[0] == "-":
            sign = -sign
        s = s[1:].strip()
    if "|" in s:
        a, b = s.split("|", 1)
        val = Number.from_literal(a.strip()) / Number.from_literal(b.strip())
    else:
        val = Number.from_literal(s)
    return -val if sign < 0 else val
