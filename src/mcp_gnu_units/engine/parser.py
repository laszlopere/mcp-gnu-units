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

"""Recursive-descent parser for unit expressions (TODO §2.4.8, grammar §4).

One function per precedence level, loosest to tightest:

    sum      : product { ('+'|'-') product }          # conformable only
    product  : juxt    { ('*'|'/'|'per') juxt }        # same precedence, left→right
    juxt     : power   { power }*                      # space = multiply, greedy
    power    : unary   [ '^' exponent ]                # right-associative
    unary    : { '-' | '~' } atom                      # negation / inverse
    atom     : NUMBER | NAME | NAME '(' args ')' | '(' sum ')'

Because ``juxt`` greedily consumes every adjacent factor *before* ``product``
re-examines a ``/``, the footgun falls out for free: ``a/b c`` parses as
``a/(b c)`` while ``a/b*c`` parses as ``(a/b)*c``. ``per`` is a synonym for ``/``
handled at the ``product`` level (and excluded from ``juxt`` continuation).
"""

from __future__ import annotations

from .ast import BinOp, Expr, FuncCall, Inverse, Juxt, Neg, Num, Power, UnitRef
from .errors import ParseError
from .lexer import Tok, Token, tokenize
from .number import Number

# Token kinds that can begin a factor (and so continue a juxtaposition run).
_FACTOR_START = {Tok.NUMBER, Tok.NAME, Tok.LPAREN, Tok.TILDE}


def parse(text: str) -> Expr:
    """Parse a complete unit expression string into an AST."""
    return _Parser(tokenize(text), text).parse()


class _Parser:
    def __init__(self, tokens: list[Token], text: str) -> None:
        self._toks = tokens
        self._text = text
        self._i = 0

    # -- token cursor ----------------------------------------------------

    def _peek(self) -> Token:
        return self._toks[self._i]

    def _advance(self) -> Token:
        tok = self._toks[self._i]
        self._i += 1
        return tok

    def _at(self, kind: Tok) -> bool:
        return self._peek().kind == kind

    def _expect(self, kind: Tok) -> Token:
        if not self._at(kind):
            raise ParseError(
                f"expected {kind.name} but found {self._peek().kind.name} in {self._text!r}"
            )
        return self._advance()

    def _is_per(self) -> bool:
        tok = self._peek()
        return tok.kind == Tok.NAME and tok.value == "per"

    # -- grammar ---------------------------------------------------------

    def parse(self) -> Expr:
        if self._at(Tok.EOF):
            raise ParseError(f"empty expression: {self._text!r}")
        node = self._sum()
        if not self._at(Tok.EOF):
            tok = self._peek()
            raise ParseError(f"unexpected {tok.kind.name} at position {tok.pos} in {self._text!r}")
        return node

    def _sum(self) -> Expr:
        node = self._product()
        while self._at(Tok.PLUS) or self._at(Tok.MINUS):
            op = "+" if self._advance().kind == Tok.PLUS else "-"
            node = BinOp(op, node, self._product())
        return node

    def _product(self) -> Expr:
        # A leading '/' (or 'per') means reciprocal: '/s' == '1/s' (e.g. hertz).
        if self._at(Tok.SLASH) or self._is_per():
            node: Expr = Num(Number.exact_int(1))
        else:
            node = self._juxt()
        while self._at(Tok.STAR) or self._at(Tok.SLASH) or self._is_per():
            if self._is_per():
                self._advance()
                op = "/"
            else:
                op = "*" if self._advance().kind == Tok.STAR else "/"
            node = BinOp(op, node, self._juxt())
        return node

    def _juxt(self) -> Expr:
        node = self._power()
        while self._peek().kind in _FACTOR_START and not self._is_per():
            node = Juxt(node, self._power())
        return node

    def _power(self) -> Expr:
        base = self._unary()
        if self._at(Tok.CARET):
            self._advance()
            return Power(base, self._exponent())
        return base

    def _exponent(self) -> Expr:
        # The exponent must reduce to a pure number; parse a tight sub-expression
        # (right-associative power) so '2^3^2', '^-1', and '^(1|3)' all work.
        return self._power()

    def _unary(self) -> Expr:
        if self._at(Tok.MINUS):
            self._advance()
            return Neg(self._unary())
        if self._at(Tok.TILDE):
            self._advance()
            return Inverse(self._unary())
        return self._atom()

    def _atom(self) -> Expr:
        tok = self._peek()
        if tok.kind == Tok.NUMBER:
            self._advance()
            return Num(tok.value)  # type: ignore[arg-type]
        if tok.kind == Tok.NAME:
            self._advance()
            if self._at(Tok.LPAREN):
                return self._funccall(str(tok.value))
            return UnitRef(str(tok.value))
        if tok.kind == Tok.LPAREN:
            self._advance()
            node = self._sum()
            self._expect(Tok.RPAREN)
            return node
        raise ParseError(f"unexpected {tok.kind.name} at position {tok.pos} in {self._text!r}")

    def _funccall(self, name: str) -> Expr:
        self._expect(Tok.LPAREN)
        args: list[Expr] = []
        if not self._at(Tok.RPAREN):
            args.append(self._sum())
            while self._at(Tok.COMMA):
                self._advance()
                args.append(self._sum())
        self._expect(Tok.RPAREN)
        return FuncCall(name, tuple(args))
