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

"""Tokenizer for unit expressions (TODO §2.4.8, grammar §2 of definitions-format).

Whitespace is discarded — it only delimits tokens. Juxtaposition (multiplication
by adjacency) is therefore NOT a token; the parser infers it from two adjacent
factors with no operator between them, which is exactly what makes ``a/b c`` parse
as ``a/(b c)``. The ``|`` fraction operator is resolved HERE: ``1|2`` and
``4|3`` each lex into a single exact ``NUMBER`` token, so ``4|3 pi`` becomes
``[NUMBER(4/3), NAME(pi)]`` and reads as ``(4/3)·pi``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .errors import ParseError
from .number import Number


class Tok(Enum):
    NUMBER = auto()
    NAME = auto()
    STAR = auto()
    SLASH = auto()
    PLUS = auto()
    MINUS = auto()
    CARET = auto()  # ^ or **
    TILDE = auto()  # ~ inverse
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    SEMI = auto()
    COMMA = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    kind: Tok
    value: object  # Number for NUMBER, str for NAME, else None
    pos: int


# Characters that terminate a name / are operators or punctuation.
_SPECIAL = set("+-*/^|~()[];,#")

_SIMPLE = {
    "+": Tok.PLUS,
    "-": Tok.MINUS,
    "/": Tok.SLASH,
    "~": Tok.TILDE,
    "(": Tok.LPAREN,
    ")": Tok.RPAREN,
    "[": Tok.LBRACKET,
    "]": Tok.RBRACKET,
    ";": Tok.SEMI,
    ",": Tok.COMMA,
}


def tokenize(text: str) -> list[Token]:
    """Lex a unit expression into tokens (terminated by an EOF token)."""
    tokens: list[Token] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c == "#":  # comment to end of line (loader usually strips these first)
            break
        if c == "*":
            if i + 1 < n and text[i + 1] == "*":
                tokens.append(Token(Tok.CARET, None, i))
                i += 2
            else:
                tokens.append(Token(Tok.STAR, None, i))
                i += 1
            continue
        if c == "^":
            tokens.append(Token(Tok.CARET, None, i))
            i += 1
            continue
        if c in _SIMPLE:
            tokens.append(Token(_SIMPLE[c], None, i))
            i += 1
            continue
        if c == "|":  # a bare pipe with no preceding number is malformed
            raise ParseError(f"unexpected '|' at position {i} in {text!r}")
        if _starts_number(text, i):
            start = i
            value, i = _lex_number(text, i)
            tokens.append(Token(Tok.NUMBER, value, start))
            continue
        # otherwise a name: greedily consume name characters
        start = i
        while i < n and not text[i].isspace() and text[i] not in _SPECIAL:
            i += 1
        tokens.append(Token(Tok.NAME, text[start:i], start))
    tokens.append(Token(Tok.EOF, None, n))
    return tokens


def _starts_number(text: str, i: int) -> bool:
    c = text[i]
    if c.isdigit():
        return True
    return c == "." and i + 1 < len(text) and text[i + 1].isdigit()


def _lex_number(text: str, i: int) -> tuple[Number, int]:
    """Lex a number, folding a trailing ``|number`` fraction into one value."""
    value, i = _lex_simple_number(text, i)
    while i < len(text) and text[i] == "|":
        i += 1
        denom, i = _lex_simple_number(text, i)
        value = value / denom
    return value, i


def _lex_simple_number(text: str, i: int) -> tuple[Number, int]:
    n = len(text)
    start = i
    while i < n and text[i].isdigit():
        i += 1
    if i < n and text[i] == ".":
        i += 1
        while i < n and text[i].isdigit():
            i += 1
    # exponent: only consume 'e'/'E' when a real exponent (optional sign + digit) follows
    if i < n and text[i] in "eE":
        j = i + 1
        if j < n and text[j] in "+-":
            j += 1
        if j < n and text[j].isdigit():
            j += 1
            while j < n and text[j].isdigit():
                j += 1
            i = j
    lexeme = text[start:i]
    if lexeme in ("", ".") or not any(ch.isdigit() for ch in lexeme):
        raise ParseError(f"malformed number at position {start} in {text!r}")
    return Number.from_literal(lexeme), i
