from __future__ import annotations

import importlib
from typing import Annotated, Any, Literal, Tuple, Union

import pytest

from equivalib import ValueRange


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


def test_boolean_expression_true_is_boolean_constant_true():
    assert true_expr() == bool_const(True)


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


def test_generate_none_tree():
    generate = core_attr("generate")
    assert generate(None, true_expr(), {}) == {None}


def test_generate_union_tree_exhaustively():
    generate = core_attr("generate")
    assert generate(Union[Literal["blue"], Literal["red"]], true_expr(), {}) == {"blue", "red"}


def test_generate_named_bool_defaults_to_all():
    generate = core_attr("generate")
    Name = core_attr("Name")
    assert generate(Annotated[bool, Name("X")], true_expr(), {}) == {True, False}


def test_generate_named_union_defaults_to_all():
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Annotated[Union[Literal["blue"], Literal["red"]], Name("X")]
    assert generate(tree, true_expr(), {}) == {"blue", "red"}


def test_generate_accepts_name_and_value_range_in_either_metadata_order():
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Annotated[int, Name("X"), ValueRange(1, 2)]
    assert generate(tree, true_expr(), {}) == {1, 2}


def test_generate_named_bool_arbitrary_picks_canonical_first():
    generate = core_attr("generate")
    Name = core_attr("Name")
    assert generate(Annotated[bool, Name("X")], true_expr(), {"X": "arbitrary"}) == {True}


def test_generate_named_tuple_arbitrary_picks_one_tuple_witness():
    generate = core_attr("generate")
    Name = core_attr("Name")
    # Canonical order: True < False (True sorts first), so (True, True) is the
    # lexicographically-first tuple under the canonical total order.
    assert generate(Annotated[Tuple[bool, bool], Name("X")], true_expr(), {"X": "arbitrary"}) == {(True, True)}


def test_generate_repeated_named_tuples_share_one_atomic_value():
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[
        Annotated[Tuple[bool, bool], Name("X")],
        Annotated[Tuple[bool, bool], Name("X")],
    ]
    assert generate(tree, true_expr(), {"X": "all"}) == {
        ((True, True), (True, True)),
        ((True, False), (True, False)),
        ((False, True), (False, True)),
        ((False, False), (False, False)),
    }


def test_generate_same_label_means_same_value():
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("X")]]
    assert generate(tree, true_expr(), {"X": "all"}) == {(True, True), (False, False)}


def test_generate_different_labels_with_same_domain_remain_independent():
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    assert generate(tree, true_expr(), {"X": "all", "Y": "all"}) == {
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    }


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


def test_generate_with_add_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Add = core_attr("Add")
    Eq = core_attr("Eq")
    tree = Annotated[int, ValueRange(0, 4), Name("X")]
    constraint = Eq(Add(ref("X"), int_const(1)), int_const(3))
    assert generate(tree, constraint, {"X": "all"}) == {2}


def test_generate_with_sub_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Sub = core_attr("Sub")
    tree = Annotated[int, ValueRange(0, 4), Name("X")]
    constraint = Eq(Sub(ref("X"), int_const(1)), int_const(1))
    assert generate(tree, constraint, {"X": "all"}) == {2}


def test_generate_with_mul_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Mul = core_attr("Mul")
    tree = Annotated[int, ValueRange(0, 4), Name("X")]
    constraint = Eq(Mul(ref("X"), int_const(2)), int_const(4))
    assert generate(tree, constraint, {"X": "all"}) == {2}


def test_generate_with_floor_div_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    FloorDiv = core_attr("FloorDiv")
    tree = Annotated[int, ValueRange(0, 5), Name("X")]
    constraint = Eq(FloorDiv(ref("X"), int_const(2)), int_const(1))
    assert generate(tree, constraint, {"X": "all"}) == {2, 3}


def test_generate_with_mod_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Mod = core_attr("Mod")
    tree = Annotated[int, ValueRange(0, 5), Name("X")]
    constraint = Eq(Mod(ref("X"), int_const(2)), int_const(1))
    assert generate(tree, constraint, {"X": "all"}) == {1, 3, 5}


def test_generate_with_neg_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Neg = core_attr("Neg")
    tree = Annotated[int, ValueRange(0, 4), Name("X")]
    constraint = Eq(Neg(ref("X")), int_const(-2))
    assert generate(tree, constraint, {"X": "all"}) == {2}


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


@pytest.mark.parametrize("method", ["arbitrary", "uniform_random", "arbitrarish_randomish"])
def test_super_methods_preserve_non_empty_singleton_subset_when_satisfiable(method):
    generate = core_attr("generate")
    Name = core_attr("Name")
    Ne = core_attr("Ne")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    constraint = Ne(ref("X"), ref("Y"))
    all_results = generate(tree, constraint, {"X": "all", "Y": "all"})
    witness_result = generate(tree, constraint, {"X": method, "Y": method})
    assert all_results
    assert len(witness_result) == 1
    assert witness_result <= all_results


def test_generate_name_free_tree_matches_values():
    generate = core_attr("generate")
    values = core_attr("values")
    tree = Tuple[Union[Literal["blue"], Literal["red"]], Annotated[int, ValueRange(1, 2)]]
    expected = {
        ("blue", 1),
        ("blue", 2),
        ("red", 1),
        ("red", 2),
    }
    assert values(tree) == expected
    assert generate(tree) == expected


def test_values_exhaust_unnamed_tuple_tree():
    values = core_attr("values")
    assert values(Tuple[bool, Literal["N\\A"]]) == {(True, "N\\A"), (False, "N\\A")}


def test_values_support_none_and_union():
    values = core_attr("values")
    assert values(Union[Literal["blue"], None]) == {"blue", None}


def test_values_reject_named_tree():
    values = core_attr("values")
    Name = core_attr("Name")
    with pytest.raises(ValueError):
        values(Annotated[bool, Name("X")])


def test_mentioned_labels_collects_labels_from_expression():
    mentioned_labels = core_attr("mentioned_labels")
    And = core_attr("And")
    Lt = core_attr("Lt")
    Gt = core_attr("Gt")
    expr = And(Lt(ref("X"), ref("Y")), Gt(ref("X"), int_const(0)))
    assert mentioned_labels(expr) == {"X", "Y"}


def test_mentioned_labels_deduplicates_repeated_references():
    And = core_attr("And")
    Eq = core_attr("Eq")
    Or = core_attr("Or")
    mentioned_labels = core_attr("mentioned_labels")
    expr = Or(Eq(ref("X"), bool_const(True)), And(Eq(ref("X"), bool_const(False)), Eq(ref("Y"), bool_const(True))))
    assert mentioned_labels(expr) == {"X", "Y"}


def test_generate_rejects_empty_name_label():
    generate = core_attr("generate")
    Name = core_attr("Name")
    with pytest.raises(ValueError):
        generate(Annotated[bool, Name("")], true_expr(), {})


def test_generate_rejects_invalid_value_range_bounds():
    generate = core_attr("generate")
    with pytest.raises(ValueError):
        generate(Annotated[int, ValueRange(4, 3)], true_expr(), {})


def test_generate_rejects_plain_int_in_core():
    generate = core_attr("generate")
    with pytest.raises(ValueError):
        generate(int, true_expr(), {})


def test_generate_rejects_duplicate_name_metadata():
    generate = core_attr("generate")
    Name = core_attr("Name")
    with pytest.raises(ValueError):
        generate(Annotated[bool, Name("X"), Name("Y")], true_expr(), {})


def test_generate_rejects_duplicate_value_range_metadata():
    generate = core_attr("generate")
    with pytest.raises(ValueError):
        generate(Annotated[int, ValueRange(0, 1), ValueRange(2, 3)], true_expr(), {})


def test_generate_rejects_unknown_annotated_metadata():
    generate = core_attr("generate")
    with pytest.raises(ValueError):
        generate(Annotated[bool, "mystery"], true_expr(), {})


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


def test_generate_rejects_unknown_method_name():
    generate = core_attr("generate")
    Name = core_attr("Name")
    with pytest.raises(ValueError):
        generate(Annotated[bool, Name("X")], true_expr(), {"X": "bogus"})


def test_generate_rejects_invalid_address_on_scalar_label():
    Eq = core_attr("Eq")
    Name = core_attr("Name")
    generate = core_attr("generate")
    with pytest.raises(ValueError):
        generate(Annotated[bool, Name("X")], Eq(ref("X", (0,)), bool_const(True)), {})


def test_generate_rejects_out_of_range_tuple_address():
    Eq = core_attr("Eq")
    Name = core_attr("Name")
    generate = core_attr("generate")
    with pytest.raises(ValueError):
        generate(Annotated[Tuple[bool], Name("X")], Eq(ref("X", (1,)), bool_const(True)), {})


def test_generate_rejects_address_that_crosses_shape_boundary():
    Eq = core_attr("Eq")
    Name = core_attr("Name")
    generate = core_attr("generate")
    tree = Annotated[Union[Tuple[bool], bool], Name("X")]
    with pytest.raises(ValueError):
        generate(tree, Eq(ref("X", (0,)), bool_const(True)), {})


def test_generate_rejects_non_boolean_top_level_constraint():
    Add = core_attr("Add")
    Name = core_attr("Name")
    generate = core_attr("generate")
    with pytest.raises((TypeError, ValueError)):
        generate(Annotated[int, ValueRange(0, 2), Name("X")], Add(ref("X"), int_const(1)), {"X": "all"})


def test_generate_rejects_invalid_expression_operand_types():
    Lt = core_attr("Lt")
    Name = core_attr("Name")
    generate = core_attr("generate")
    with pytest.raises((TypeError, ValueError)):
        generate(Annotated[bool, Name("X")], Lt(ref("X"), bool_const(True)), {"X": "all"})


def test_expression_ast_is_required_not_source_string():
    generate = core_attr("generate")
    Name = core_attr("Name")
    with pytest.raises((TypeError, ValueError)):
        generate(Annotated[bool, Name("X")], "X == True", {"X": "all"})


def test_generate_supports_default_arguments():
    generate = core_attr("generate")
    assert generate(Literal[True]) == {True}
