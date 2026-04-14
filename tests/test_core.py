from __future__ import annotations

import importlib
from typing import Annotated, Any, Literal, Tuple

import pytest

from equivalib import ValueRange

pytestmark = pytest.mark.xfail(
    reason="Core API from docs/spec1.md is planned but not implemented yet.",
    strict=True,
)


def core_attr(name: str) -> Any:
    module = importlib.import_module("equivalib.core")
    return getattr(module, name)


def true_expr() -> Any:
    return core_attr("BooleanExpression")(True)


def bool_const(value: bool) -> Any:
    return core_attr("BooleanConstant")(value)


def int_const(value: int) -> Any:
    return core_attr("IntegerConstant")(value)


def ref(label: str, path: tuple[int, ...] = ()) -> Any:  # noqa: D401
    return core_attr("Reference")(label, path)


def test_core_exports_generate_and_ast_surface():
    assert core_attr("generate")
    assert core_attr("Name")
    assert core_attr("BooleanExpression")
    assert core_attr("BooleanConstant")
    assert core_attr("IntegerConstant")
    assert core_attr("Reference")
    assert core_attr("Eq")
    assert core_attr("Ne")
    assert core_attr("Lt")
    assert core_attr("Le")
    assert core_attr("Gt")
    assert core_attr("Ge")
    assert core_attr("And")
    assert core_attr("Or")
    assert core_attr("Add")
    assert core_attr("Sub")
    assert core_attr("Mul")
    assert core_attr("FloorDiv")
    assert core_attr("Mod")
    assert core_attr("Neg")


def test_generate_literal_true():
    generate = core_attr("generate")
    assert generate(Literal[True], true_expr(), {}) == {True}


def test_generate_unnamed_tuple_exhaustively_by_default():
    generate = core_attr("generate")
    assert generate(Tuple[bool, Literal["N\\A"]], true_expr(), {}) == {
        (True, "N\\A"),
        (False, "N\\A"),
    }


def test_generate_bounded_int_range():
    generate = core_attr("generate")
    assert generate(Annotated[int, ValueRange(3, 4)], true_expr(), {}) == {3, 4}


def test_generate_named_bool_defaults_to_all():
    generate = core_attr("generate")
    Name = core_attr("Name")
    assert generate(Annotated[bool, Name("X")], true_expr(), {}) == {True, False}


def test_generate_named_bool_arbitrary_picks_canonical_first():
    generate = core_attr("generate")
    Name = core_attr("Name")
    assert generate(Annotated[bool, Name("X")], true_expr(), {"X": "arbitrary"}) == {True}


def test_generate_named_tuple_arbitrary_picks_one_tuple_witness():
    generate = core_attr("generate")
    Name = core_attr("Name")
    assert generate(Annotated[Tuple[bool, bool], Name("X")], true_expr(), {"X": "arbitrary"}) == {(True, False)}


def test_generate_same_label_means_same_value():
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("X")]]
    assert generate(tree, true_expr(), {"X": "all"}) == {(True, True), (False, False)}


def test_generate_repeated_label_domains_intersect():
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[
        Annotated[int, ValueRange(1, 5), Name("X")],
        Annotated[int, ValueRange(3, 7), Name("X")],
    ]
    assert generate(tree, true_expr(), {"X": "all"}) == {(3, 3), (4, 4), (5, 5)}


def test_generate_empty_when_repeated_label_domains_do_not_overlap():
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[
        Annotated[int, ValueRange(1, 2), Name("X")],
        Annotated[int, ValueRange(5, 6), Name("X")],
    ]
    assert generate(tree, true_expr(), {"X": "all"}) == set()


def test_generate_with_equality_constraint_exhaustively():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    constraint = Eq(ref("X"), ref("Y"))
    assert generate(tree, constraint, {"X": "all", "Y": "all"}) == {(True, True), (False, False)}


def test_generate_with_inequality_constraint_exhaustively():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Ne = core_attr("Ne")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    constraint = Ne(ref("X"), ref("Y"))
    assert generate(tree, constraint, {"X": "all", "Y": "all"}) == {(True, False), (False, True)}


def test_generate_with_address_constraint_on_named_tuple():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Ne = core_attr("Ne")
    tree = Annotated[Tuple[bool, bool], Name("X")]
    constraint = Ne(ref("X", (0,)), ref("X", (1,)))
    assert generate(tree, constraint, {"X": "all"}) == {(True, False), (False, True)}


def test_generate_with_arithmetic_and_order_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    And = core_attr("And")
    Gt = core_attr("Gt")
    Lt = core_attr("Lt")
    tree = Tuple[
        Annotated[int, ValueRange(0, 3), Name("X")],
        Annotated[int, ValueRange(0, 3), Name("Y")],
    ]
    constraint = And(Gt(ref("X"), int_const(0)), Lt(ref("X"), ref("Y")))
    assert generate(tree, constraint, {"X": "all", "Y": "all"}) == {(1, 2), (1, 3), (2, 3)}


def test_generate_with_or_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Or = core_attr("Or")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    constraint = Or(Eq(ref("X"), bool_const(True)), Eq(ref("Y"), bool_const(True)))
    assert generate(tree, constraint, {"X": "all", "Y": "all"}) == {
        (True, True),
        (True, False),
        (False, True),
    }


def test_generate_contradiction_yields_empty_set():
    generate = core_attr("generate")
    Name = core_attr("Name")
    And = core_attr("And")
    Eq = core_attr("Eq")
    Ne = core_attr("Ne")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    constraint = And(Eq(ref("X"), ref("Y")), Ne(ref("X"), ref("Y")))
    assert generate(tree, constraint, {"X": "all", "Y": "all"}) == set()


def test_generate_arbitrary_with_shared_constraint_is_deterministic():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Ne = core_attr("Ne")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    constraint = Ne(ref("X"), ref("Y"))
    first = generate(tree, constraint, {"X": "arbitrary", "Y": "arbitrary"})
    second = generate(tree, constraint, {"X": "arbitrary", "Y": "arbitrary"})
    assert first == {(True, False)}
    assert second == {(True, False)}


def test_generate_uniform_random_always_returns_subset_of_all():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Ne = core_attr("Ne")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    constraint = Ne(ref("X"), ref("Y"))
    all_results = generate(tree, constraint, {"X": "all", "Y": "all"})
    random_result = generate(tree, constraint, {"X": "uniform_random", "Y": "uniform_random"})
    assert len(random_result) == 1
    assert random_result <= all_results


def test_generate_arbitrarish_randomish_always_returns_subset_of_all():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Ne = core_attr("Ne")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    constraint = Ne(ref("X"), ref("Y"))
    all_results = generate(tree, constraint, {"X": "all", "Y": "all"})
    randomish_result = generate(tree, constraint, {"X": "arbitrarish_randomish", "Y": "arbitrarish_randomish"})
    assert len(randomish_result) == 1
    assert randomish_result <= all_results


def test_values_exhaust_unnamed_tuple_tree():
    values = core_attr("values")
    assert values(Tuple[bool, Literal["N\\A"]]) == {(True, "N\\A"), (False, "N\\A")}


def test_mentioned_labels_collects_labels_from_expression():
    mentioned_labels = core_attr("mentioned_labels")
    And = core_attr("And")
    Lt = core_attr("Lt")
    Gt = core_attr("Gt")
    expr = And(Lt(ref("X"), ref("Y")), Gt(ref("X"), int_const(0)))
    assert mentioned_labels(expr) == {"X", "Y"}


def test_generate_rejects_empty_name_label():
    generate = core_attr("generate")
    Name = core_attr("Name")
    with pytest.raises(ValueError):
        generate(Annotated[bool, Name("")], true_expr(), {})


def test_generate_rejects_plain_int_in_core():
    generate = core_attr("generate")
    with pytest.raises(ValueError):
        generate(int, true_expr(), {})


def test_generate_rejects_constraint_on_missing_label():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    with pytest.raises(ValueError):
        generate(Annotated[bool, Name("X")], Eq(ref("Y"), bool_const(True)), {})


def test_generate_rejects_unknown_method_label():
    generate = core_attr("generate")
    Name = core_attr("Name")
    with pytest.raises(ValueError):
        generate(Annotated[bool, Name("X")], true_expr(), {"Y": "all"})


def test_expression_ast_is_required_not_source_string():
    generate = core_attr("generate")
    Name = core_attr("Name")
    with pytest.raises((TypeError, ValueError)):
        generate(Annotated[bool, Name("X")], "X == True", {"X": "all"})


def test_generate_supports_default_arguments():
    generate = core_attr("generate")
    assert generate(Literal[True]) == {True}
