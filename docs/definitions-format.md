# The `definitions.units` language — format & grammar specification

This document describes the syntax of the GNU units database file we bundle at
`src/mcp_gnu_units/data/definitions.units`. It is the contract our pure-Python
parser/engine (TODO §2.4, §13 ENGINE) must implement.

**Scope of authority.** GNU units publishes no formal grammar; the canonical
references are the [GNU units manual](https://www.gnu.org/software/units/manual/)
(prose + examples) and the C source (a hand-written recursive-descent parser).
This spec is *derived* from the manual plus a scan of the bundled file, and is
**pinned to definitions data version 3.26** (GNU units 2.27, dated 2026-02-25 —
see [`NOTICE`](../NOTICE)). Every rule below that affects evaluation MUST be
validated against the real `units` binary as a test oracle (TODO §13); the
precedence rules in particular are notorious footguns. Where this document and
the binary disagree, the binary wins and this document is the bug.

The grammar uses ISO-ish EBNF: `|` alternation, `[...]` optional, `{...}` zero or
more, `(...)` grouping, `'x'` literal. (Note: `|` here is EBNF alternation, not
the units fraction operator, which is written as the literal `'|'`.)

---

## 1. File structure

A units database is a sequence of **physical lines** combined into **logical
lines**, processed top to bottom. Order matters: a unit may only be defined in
terms of units, prefixes, and functions defined *earlier* in the file (forward
references are not resolved).

```ebnf
file        = { logical-line } ;
logical-line= ( definition | directive | blank ) , newline ;
```

### 1.1 Comments

`#` begins a comment that runs to end of line. Comments may be a whole line or
trail a definition. There is no block-comment syntax.

```
hour                    60 min       # trailing comment
# whole-line comment
```

### 1.2 Line continuation

A backslash `\` as the **last character** of a physical line joins it to the
next physical line. Used heavily for long function definitions and piecewise
tables. A comment may not follow the `\` on the same physical line.

```
tempF(x) units=[1;K] domain=[-459.67,) range=[0,) \
    (x+(-32)) degF + stdtemp ; (tempF+(-stdtemp))/degF + 32
```

### 1.3 Whitespace

Spaces and tabs separate tokens; runs of whitespace are equivalent to one space.
Leading/trailing whitespace on a line is insignificant **except** that a space
between two factors is the multiplication operator (§4.1) — whitespace is *not*
always ignorable inside expressions.

### 1.4 Encoding

The file is UTF-8. Unit *names* may contain non-ASCII letters (e.g. `dönüm`,
`mål`, `Å`). Such names are typically guarded inside `!utf8 … !endutf8` blocks
(§3.6) so they are only defined when the output device supports UTF-8.

---

## 2. Lexical elements

### 2.1 Identifiers (unit / prefix / function names)

Names are whitespace-delimited tokens. They are far more permissive than typical
programming identifiers and may include letters (incl. non-ASCII), digits, and
punctuation such as `_ . ' % - ^ + ( ) [ ]` — but several of those characters
are *also* operators, so the surrounding form (see §3) determines tokenization:

- A trailing `-` marks a **prefix** definition (§3.1): `kilo-`, `quetta-`.
- A trailing `(params)` marks a **function** definition (§3.4): `tempC(x)`.
- A trailing `[unit]` marks a **piecewise-table** definition (§3.5): `gasmark[degR]`.

Examples of real names: `s`, `kg`, `h_SI`, `tempreaumur`, `npsOD`, `1|8` is
*not* a name (it is a number). Some names legitimately contain digits (`h2o`,
`co2`, `pi`), so a name is not required to start with a letter, but a token that
parses as a number is a number, not a name.

### 2.2 Numbers

```ebnf
number   = mantissa [ exp ] | fraction ;
mantissa = digits [ '.' digits ] | '.' digits ;   (* .0625 is valid *)
exp      = ('e'|'E') [ '+' | '-' ] digits ;        (* 6.62607015e-34 *)
fraction = number '|' number ;                     (* 1|2, 4|3, 1|299792458 *)
```

`|` is the **fraction operator** (§4.1): `1|2` is one half, evaluated exactly.
Its operands are numbers (and it has the highest precedence), so `4|3 pi` is
`(4/3)·pi`. Scientific notation uses `e`/`E`. A leading decimal point is allowed
(`.0625`).

### 2.3 Operators and punctuation

| Token        | Meaning                                                        |
|--------------|---------------------------------------------------------------|
| `|`          | numeric fraction / division, highest precedence (§4.1)        |
| `^` `**`     | exponentiation (the DB uses `^`; `**` is accepted by units)   |
| space        | multiplication by juxtaposition (§4.1)                         |
| `*` `/`      | multiplication / division (`per` is a synonym for `/`)        |
| `+`          | addition (of conformable quantities)                           |
| `-`          | unary negation; subtraction is written `+ -x` (see §4.2)       |
| `~`          | functional **inverse** application: `~f(y)` (§4.3)             |
| `( )`        | grouping; also delimit function parameter lists                |
| `[ ]`        | delimit the unit tag of a function (`units=[…]`) or table head |
| `;`          | separates a function's forward and inverse expressions (§3.4) |
| `!`          | leads a directive (column 1) or marks a primitive unit (§3.2) |
| `#`          | comment                                                        |

---

## 3. Definitions

```ebnf
definition = prefix-def
           | primitive-def
           | unit-def
           | function-def
           | table-def ;
```

### 3.1 Prefix definitions

A name ending in `-` defines a prefix. Its value is a number or an expression
that the prefix multiplies onto whatever it is attached to.

```ebnf
prefix-def = prefix-name '-' value-expr ;
```

```
quetta-                 1e30
kilo-                   1000
quarter-                1|4
```

A prefix attaches to a following unit with no space (`kilometer`, `kquetta`…).
Resolving `prefix+unit` vs. a standalone unit is a parser concern, not a syntax
one: units tries the longest matching prefix then requires the remainder to be a
defined unit.

### 3.2 Primitive (base) units

A name followed by `!` declares a **primitive** unit that reduces to itself — the
irreducible base of a dimension. `!dimensionless` declares a primitive that is
nonetheless dimensionless (e.g. angle, information).

```ebnf
primitive-def = unit-name '!' [ 'dimensionless' ] ;
```

```
s         !                 # second   — SI base
m         !                 # metre    — SI base
kg        !                 # kilogram — SI base
radian    !dimensionless    # plane angle
bit       !                 # information
```

### 3.3 Ordinary unit definitions

A name followed by a value expression (§4) defines a unit equal to that
expression. This is the most common form.

```ebnf
unit-def = unit-name value-expr ;
```

```
minute                  60 s
newton                  kg m / s^2
pascal                  N/m^2
inch                    2.54 cm
foot                    12 inch
```

A unit may be *dimensionless-by-reduction* (reduces to a pure number), e.g.
`degree  pi/180`.

### 3.4 Nonlinear / function units

A name with a parenthesized parameter list defines a **nonlinear** unit via a
forward conversion and (optionally) its inverse, separated by `;`.

```ebnf
function-def = func-name '(' params ')' { func-attr } forward-expr
                                         [ ';' inverse-expr ] ;
params       = param { ',' param } ;
func-attr    = 'units' '=' '[' dim { (';'|',') dim } ']'
             | 'domain' '=' interval { ',' interval }
             | 'range'  '=' interval
             | 'noerror' ;
interval     = ('['|'(') [ number ] ',' [ number ] (']'|')') ;  (* ISO interval *)
```

- **`units=[in;out]`** declares the dimensions of the parameter(s) and result.
  For a single parameter the two halves are `;`-separated (`[1;K]`, `[m;m^2]`);
  for multiple parameters the *input* dimensions are `,`-separated
  (`[K,mph]`).
- **`domain=`** / **`range=`** give valid input/output intervals using ISO
  half-open notation: `[a,b]` closed, `(a,b)` open, an empty endpoint means
  unbounded (`[0,)` is "≥ 0"). Multiple comma-separated intervals pair with
  multiple parameters.
- **`noerror`** suppresses out-of-domain errors.
- The text **before `;`** is the forward expression (parameter → result); the
  text **after `;`** is the inverse (result value, referenced by the function's
  own name, → parameter).

```
tempC(x) units=[1;K] domain=[-273.15,) range=[0,) \
                             x K + stdtemp ; (tempC +(-stdtemp))/K

circum(r)          units=[m;m]   range=[0,) 2 pi r ; circum/ 2 pi

windchillpower(T,speed) units=[K,mph] domain=[170,283.15],[3,) \
                 (12.1452 + 11.6222 sqrt(speed/(m/s)) +- 1.1622 speed/(m/s)) \
                   * (33 +- ~tempC(T)) W/m^2
```

A zero-parameter form `name()` aliases an existing function: `spherevol()
spherevolume`.

### 3.5 Piecewise-linear table units

A name followed by `[outunit]` and a continued list of `input output` number
pairs defines a unit by **linear interpolation** between the tabulated points.
The bracketed unit is the dimension of the second column.

```ebnf
table-def = unit-name '[' unit-expr ']' { number number } ;
```

```
gasmark[degR] \
  .0625    634.67 \
  .125     659.67 \
  .25      684.67 \
  1        734.67 \
  ...
```

The file opens with one such table named `test` (`test[micron*pi]`), used by
`units --check` to exercise interpolation; it is genuine upstream content and is
shipped verbatim.

---

## 4. Expression grammar (`value-expr`)

The right-hand side of a definition, and any user-entered conversion query, is a
unit expression.

```ebnf
value-expr = sum ;
sum        = product { ('+'|'-') product } ;          (* conformable only *)
product    = power { ('*'|'/') power } ;               (* same precedence, L→R *)
power      = juxt [ ('^'|'**') exponent ] ;
juxt       = unary { unary } ;                         (* space = multiply *)
unary      = [ '-' ] [ '~' ] atom ;
atom       = number
           | name                                       (* unit / prefix+unit *)
           | func-name '(' value-expr { ',' value-expr } ')'
           | '(' value-expr ')' ;
exponent   = signed-number | '(' value-expr ')' ;       (* must reduce to a pure number *)
```

> **Caveat:** the EBNF above is a *readable approximation*. It does not by itself
> capture units' real precedence (juxtaposition binds tighter than `*`/`/`; see
> §4.1), which a faithful parser must encode in its grammar levels or
> precedence-climbing table. Treat §4.1 as normative over the EBNF.

### 4.1 Operator precedence (highest → lowest)

This is the part to get right and oracle-test. Confirmed against the bundled DB:

1. **`|`** — numeric fraction. `4|3 pi` = `(4/3)·pi`; `spherevolume/4|3 pi`
   means `spherevolume/((4/3)·pi)`.
2. **`^` / `**`** — exponentiation. The exponent must reduce to a number;
   fractional exponents are parenthesized in the DB (`cube^(1|3)`, `m^(1|3)`).
3. **unary `-`**, **`~`** (inverse), **function application**, **`( )`**.
4. **juxtaposition** (a space) — multiplication. *Binds tighter than `*` and
   `/`.*
5. **`*` and `/`** — same precedence, left-to-right. `per` is a synonym for `/`.
6. **binary `+` / `-`** — lowest; only meaningful between conformable quantities.

**The footgun, proven from the data.** `circum(r)`'s inverse is written
`circum/ 2 pi`. Because juxtaposition (level 4) binds tighter than `/` (level 5),
this parses as `circum / (2 pi)` = `C/(2π)` = the radius — correct. A naive
left-to-right reading `(circum/2)·pi` would be wrong. So: **everything to the
right of a `/`, up to the next `*`/`/` or `+`/`-`, multiplies into the
denominator.** Equivalently `a/b c` = `a/(b c)`, and `a/b*c` = `(a/b)*c`.

### 4.2 Subtraction and signs

units avoids bare binary `-` because a `-` is easily mistaken for a number's
sign. The DB writes subtraction as **`+` followed by unary `-`**:

- `(tempC +(-stdtemp))/K`  → `tempC - stdtemp`, then `/K`.
- `33 +- ~tempC(T)`         → `33 + (-(~tempC(T)))` = `33 - ~tempC(T)`.

So `+-` is **not** a single operator: it is binary `+` then unary negation. A
parser should accept binary `-` too (the manual permits it) but must treat a
`-` glued to a number as that number's sign.

### 4.3 The inverse operator `~`

`~f(arg)` applies the **inverse** of function `f` to `arg`. Used when building
one nonlinear unit from another: `circum_d`'s inverse is `2 ~circum(circum_d)`
(diameter = 2 × inverse-circumference). `~` applies to the function call to its
right.

---

## 5. Directives

Directives begin with `!` in column 1 and control parsing rather than defining
units. Counts below are occurrences in data v3.26.

```ebnf
directive = '!set' name value
          | '!var' name { value } | '!varnot' name { value } | '!endvar'
          | '!message' text
          | '!prompt' text
          | '!include' path
          | '!unitlist' name unit-expr { ';' unit-expr }
          | '!utf8' | '!endutf8'
          | '!locale' name | '!endlocale' ;
```

| Directive             | Purpose                                                        |
|-----------------------|----------------------------------------------------------------|
| `!set VAR value`      | Set a default for an environment variable (e.g. `UNITS_ENGLISH US`). |
| `!var VAR v1 v2 …`    | Begin a block included **iff** `VAR` equals one of the listed values (like `#if`). |
| `!varnot VAR v1 …`    | Begin a block included **iff** `VAR` matches **none** of the values. |
| `!endvar`             | End a `!var`/`!varnot` block.                                   |
| `!message text`       | Emit `text` to stderr when this point is reached (used inside `!var` blocks for diagnostics). |
| `!prompt text`        | Set the interactive prompt suffix (e.g. `(SI)`).               |
| `!include path`       | Include another units file at this point.                      |
| `!unitlist name a;b;c`| Define a named multi-unit display list (`hms hr;min;sec`).      |
| `!utf8` / `!endutf8`  | Block active only when UTF-8 output is available.              |
| `!locale name` / `!endlocale` | Block active only under the matching locale (`en_US`, `en_GB`). |

```
!set UNITS_ENGLISH US
!var UNITS_SYSTEM si
!message SI units selected
!prompt (SI)
!endvar
!unitlist hms hr;min;sec
```

Conditional blocks (`!var`/`!varnot`/`!utf8`/`!locale`) nest and gate whether the
enclosed definitions are added to the symbol table.

---

## 6. Implementation notes for our engine

These are not part of the *format* but flow directly from it (TODO §2.4/§13):

- **Two-pass-free, ordered loading.** Definitions resolve against earlier ones;
  a single forward pass with an accumulating symbol table is sufficient and
  matches units' own behaviour.
- **Prefix vs unit disambiguation** (§3.1) is longest-prefix-match then
  defined-remainder, not a syntactic distinction.
- **Numbers stay exact where possible.** Fractions (`1|2`) and integer math
  should use `fractions.Fraction` / `decimal.Decimal` to preserve the
  exact/inexact verdict (TODO numerics §2.1.6). `1|299792458` must not be
  flattened to a lossy float.
- **Nonlinear units** (§3.4) carry a forward and inverse closure plus
  domain/range checks; `noerror` toggles whether out-of-range raises.
- **Conditional directives** (§5) must be evaluated against a variable
  environment to decide which definitions exist — our default environment should
  mirror units' (`UNITS_SYSTEM=default`, `UNITS_ENGLISH=US`) unless we expose
  configuration.
- **Oracle tests are mandatory** (TODO §13): diff our reductions against the real
  `units` binary across a DB sample, with golden pins for known answers
  (`1 mi → 1.609344 km`, `0 degC → 32 degF`, `1 kW*h → 3.6e6 J`). The binary is
  a dev/test dependency only — never shipped or invoked at runtime.

---

## 7. Coverage checklist

Constructs this spec covers, each present in data v3.26:

- [x] comments (`#`) and line continuation (`\`)
- [x] prefix definitions (trailing `-`)
- [x] primitive units (`!`, `!dimensionless`)
- [x] ordinary unit definitions
- [x] nonlinear/function units (`name(x)`, `units=`, `domain=`, `range=`, `noerror`, `;` inverse, `~`)
- [x] piecewise-linear table units (`name[unit]` + pairs)
- [x] numbers: integer, decimal, scientific, exact fractions (`|`)
- [x] expression operators and precedence (juxtaposition vs `/`; `+ -x` subtraction)
- [x] directives: `!set`, `!var`/`!varnot`/`!endvar`, `!message`, `!prompt`, `!include`, `!unitlist`, `!utf8`/`!endutf8`, `!locale`/`!endlocale`
