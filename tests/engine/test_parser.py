"""P1 — parse-shape tests for the precedence footguns (TODO §2.4.8)."""

from fractions import Fraction

import pytest

from mcp_gnu_units.engine.ast import BinOp, FuncCall, Inverse, Juxt, Neg, Num, Power, UnitRef
from mcp_gnu_units.engine.errors import ParseError
from mcp_gnu_units.engine.parser import parse


def test_juxtaposition_binds_tighter_than_slash():
    # a/b c  ==  a / (b c)
    tree = parse("a/b c")
    assert isinstance(tree, BinOp) and tree.op == "/"
    assert tree.left == UnitRef("a")
    assert tree.right == Juxt(UnitRef("b"), UnitRef("c"))


def test_slash_then_star_is_left_to_right():
    # a/b*c  ==  (a/b) * c
    tree = parse("a/b*c")
    assert isinstance(tree, BinOp) and tree.op == "*"
    assert isinstance(tree.left, BinOp) and tree.left.op == "/"
    assert tree.left.left == UnitRef("a")
    assert tree.left.right == UnitRef("b")
    assert tree.right == UnitRef("c")


def test_fraction_is_one_number_then_juxtaposed():
    # 4|3 pi  ==  (4/3) * pi
    tree = parse("4|3 pi")
    assert isinstance(tree, Juxt)
    assert isinstance(tree.left, Num)
    assert tree.left.value.value == Fraction(4, 3)
    assert tree.right == UnitRef("pi")


def test_circum_inverse_footgun():
    # circum/ 2 pi  ==  circum / (2 pi)   (the spec's proven example)
    tree = parse("circum/ 2 pi")
    assert isinstance(tree, BinOp) and tree.op == "/"
    assert tree.left == UnitRef("circum")
    assert isinstance(tree.right, Juxt)


def test_plus_minus_is_add_then_unary_negation():
    # 33 +- ~tempC(T)  ==  33 + (-(~tempC(T)))
    tree = parse("33 +- ~tempC(T)")
    assert isinstance(tree, BinOp) and tree.op == "+"
    assert tree.left == Num(parse("33").value)
    assert isinstance(tree.right, Neg)
    assert isinstance(tree.right.operand, Inverse)
    assert isinstance(tree.right.operand.operand, FuncCall)
    assert tree.right.operand.operand.name == "tempC"


def test_per_is_division():
    tree = parse("m per s")
    assert isinstance(tree, BinOp) and tree.op == "/"
    assert tree.left == UnitRef("m")
    assert tree.right == UnitRef("s")


def test_power_right_associative_and_parenthesized_exponent():
    assert parse("m^2") == Power(UnitRef("m"), Num(parse("2").value))
    cube = parse("m^(1|3)")
    assert isinstance(cube, Power)
    assert cube.exponent.value.value == Fraction(1, 3)


def test_newton_definition_shape():
    # kg m / s^2  ==  (kg m) / (s^2)
    tree = parse("kg m / s^2")
    assert isinstance(tree, BinOp) and tree.op == "/"
    assert tree.left == Juxt(UnitRef("kg"), UnitRef("m"))
    assert isinstance(tree.right, Power)


def test_function_call_multiple_args():
    tree = parse("windchill(T, speed)")
    assert isinstance(tree, FuncCall)
    assert tree.name == "windchill"
    assert len(tree.args) == 2


def test_empty_and_garbage_raise():
    with pytest.raises(ParseError):
        parse("")
    with pytest.raises(ParseError):
        parse("(m")
