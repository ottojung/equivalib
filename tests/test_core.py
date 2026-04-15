from __future__ import annotations

import importlib
import random
from typing import Annotated, Any, Literal, Tuple, Union

import pytest

from equivalib import ValueRange
from equivalib.core.cache import is_constraint_independent, is_guaranteed_cacheable, is_label_closed
from equivalib.core.domains import _type_aware_intersect, domain_map
from equivalib.core.eval import Unknown, _structural_eq, eval_expression, eval_expression_partial
from equivalib.core.expression import (
    Add,
    And,
    BooleanConstant,
    Eq,
    IntegerConstant,
    Mul,
    Ne,
    Neg,
    Or,
    Reference,
)
from equivalib.core.methods import apply_methods
from equivalib.core.name import Name as CoreName
from equivalib.core.normalize import normalize
from equivalib.core.order import canonical_first, canonical_sorted
from equivalib.core.types import BoolNode, LiteralNode, NamedNode, TupleNode, UnionNode
from equivalib.core.validate import validate_expression, validate_methods, validate_tree


def random_seed(seed):
    """Context manager to set the random seed for deterministic "random" generation."""

    class RandomSeedContext:
        def __enter__(self):
            self.original_state = random.getstate()
            random.seed(seed)

        def __exit__(self, exc_type, exc_val, exc_tb):
            random.setstate(self.original_state)

    return RandomSeedContext()


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
    assert generate(Annotated[bool, Name("X")], true_expr(), {"X": "arbitrary"}) == {False}


def test_generate_named_tuple_arbitrary_picks_one_tuple_witness():
    generate = core_attr("generate")
    Name = core_attr("Name")
    # Canonical order: False < True (False sorts first), so (False, False) is the
    # lexicographically-first tuple under the canonical total order.
    assert generate(Annotated[Tuple[bool, bool], Name("X")], true_expr(), {"X": "arbitrary"}) == {(False, False)}


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
    assert first == {(False, True)}
    assert second == {(False, True)}


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


@pytest.mark.parametrize("method", ["arbitrary", "uniform_random"])
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


def test_generate_rejects_non_string_name_label():
    generate = core_attr("generate")
    Name = core_attr("Name")
    with pytest.raises(ValueError):
        generate(Annotated[bool, Name(1)], true_expr(), {})


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


# ==========================================================================
# Additional edge-case tests
# ==========================================================================

# --------------------------------------------------------------------------
# Mixed named/unnamed trees
# --------------------------------------------------------------------------


def test_generate_mixed_unnamed_literal_and_named_bool():
    """Unnamed Literal[3] expands to {3}; named bool expands per assignment."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[Literal[3], Annotated[bool, Name("X")]]
    assert generate(tree, true_expr(), {}) == {(3, True), (3, False)}


def test_generate_mixed_unnamed_bool_and_named_bool():
    """An unnamed bool expands fully for every named assignment."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[bool, Annotated[bool, Name("X")]]
    assert generate(tree, true_expr(), {}) == {
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    }


def test_generate_mixed_unnamed_int_range_and_named_bool():
    """Unnamed IntRange expands fully for every named assignment."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[Annotated[int, ValueRange(0, 1)], Annotated[bool, Name("X")]]
    assert generate(tree, true_expr(), {}) == {
        (0, True),
        (0, False),
        (1, True),
        (1, False),
    }


def test_generate_mixed_unnamed_union_and_named_bool():
    """Unnamed union in mixed tree expands to all its values."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[Union[Literal["a"], Literal["b"]], Annotated[bool, Name("X")]]
    assert generate(tree, true_expr(), {}) == {
        ("a", True),
        ("a", False),
        ("b", True),
        ("b", False),
    }


def test_generate_mixed_unnamed_none_and_named_bool():
    """Unnamed None in mixed tree expands to {None}."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[None, Annotated[bool, Name("X")]]
    assert generate(tree, true_expr(), {}) == {(None, True), (None, False)}


# --------------------------------------------------------------------------
# Normalize edge cases
# --------------------------------------------------------------------------


def test_normalize_multi_value_literal_expands_to_union():
    """Literal[True, False] normalizes to a union of two singletons."""
    generate = core_attr("generate")
    assert generate(Literal[True, False]) == {True, False}


def test_normalize_nested_union_values():
    """Nested unions produce the union of all their values."""
    generate = core_attr("generate")
    tree = Union[Literal["a"], Union[Literal["b"], Literal["c"]]]
    assert generate(tree) == {"a", "b", "c"}


def test_normalize_pep604_union_values():
    """PEP 604 unions (``A | B``) normalize like typing.Union."""
    generate = core_attr("generate")
    tree = Literal["a"] | Literal["b"]
    assert generate(tree) == {"a", "b"}


def test_normalize_rejects_non_hashable_literal_value():
    generate = core_attr("generate")
    with pytest.raises(ValueError):
        generate(Literal[[]])


def test_normalize_annotated_name_before_value_range():
    """Name metadata before ValueRange (reverse order) should work."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Annotated[int, Name("X"), ValueRange(5, 7)]
    assert generate(tree, true_expr(), {}) == {5, 6, 7}


# --------------------------------------------------------------------------
# Validate: address on union-typed labels
# --------------------------------------------------------------------------


def test_generate_address_on_union_of_same_arity_tuples():
    """A path into a union where every branch is a tuple of the same arity is valid."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    # Both branches have arity 1; address (0,) is valid.
    tree = Annotated[Union[Tuple[bool], Tuple[bool]], Name("X")]
    constraint = Eq(ref("X", (0,)), bool_const(True))
    result = generate(tree, constraint, {"X": "all"})
    assert result == {(True,)}


def test_generate_rejects_address_out_of_range_on_all_union_branches():
    """Address out of range on all union branches must be rejected."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    tree = Annotated[Union[Tuple[bool], Tuple[bool]], Name("X")]
    with pytest.raises(ValueError):
        generate(tree, Eq(ref("X", (1,)), bool_const(True)), {})


def test_generate_rejects_address_valid_only_in_first_union_branch():
    """A path must be valid in every union branch, not just the first."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    tree = Annotated[Union[Tuple[Tuple[bool]], Tuple[bool]], Name("X")]
    with pytest.raises(ValueError):
        generate(tree, Eq(ref("X", (0, 0)), bool_const(True)), {})


def test_validate_rejects_non_int_path_element():
    """A Reference with a non-int path element (e.g. str) must be rejected."""
    tree_node = NamedNode("X", TupleNode((BoolNode(),)))
    # Python does not enforce type annotations at runtime, so this constructs fine
    expr = Reference("X", ("0",))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="plain int"):
        validate_expression(expr, tree_node)


def test_validate_rejects_bool_path_element():
    """A Reference with a bool path element must be rejected (bool is not a plain int index)."""
    tree_node = NamedNode("X", TupleNode((BoolNode(),)))
    expr = Reference("X", (True,))  # bool is a subclass of int, so this type-checks
    with pytest.raises(ValueError, match="plain int"):
        validate_expression(expr, tree_node)


def test_generate_rejects_path_when_repeated_label_has_non_tuple_occurrence():
    """Repeated labels with mixed shapes should reject tuple-path references."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    tree = Tuple[
        Annotated[Tuple[bool], Name("X")],
        Annotated[bool, Name("X")],
    ]
    with pytest.raises(ValueError):
        generate(tree, Eq(ref("X", (0,)), bool_const(True)), {})


def test_generate_address_on_nested_union_of_tuples():
    """A path into a nested union of tuples (Union[A, Union[B, C]]) is accepted."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    # normalize() will produce UnionNode([TupleNode([BoolNode]), UnionNode([TupleNode([BoolNode])])])
    # _resolve_shape must handle nested UnionNodes.
    tree = Annotated[Union[Tuple[bool], Union[Tuple[bool]]], Name("X")]
    constraint = Eq(ref("X", (0,)), bool_const(True))
    result = generate(tree, constraint, {"X": "all"})
    assert result == {(True,)}


def test_literal_node_bool_not_equal_to_int():
    """LiteralNode(True) must not compare equal to LiteralNode(1)."""
    assert LiteralNode(True) != LiteralNode(1)
    assert LiteralNode(False) != LiteralNode(0)
    assert hash(LiteralNode(True)) != hash(LiteralNode(1))


def test_generate_literal_true_not_same_as_literal_one():
    """Literal[True] and Literal[1] produce distinct IR nodes.

    At the Python runtime level, True == 1 and hash(True) == hash(1), so
    a Python set cannot hold them as distinct values.  generate() returns a
    Python set, so generate(Literal[True, 1]) == {True} is expected.

    The important property is that the LiteralNode IR nodes themselves are
    distinct (different type(), different hash) and that each singleton
    produces the expected Python value.
    """
    generate = core_attr("generate")
    assert generate(Literal[True]) == {True}
    assert generate(Literal[1]) == {1}
    # Due to Python set semantics (True == 1), the union collapses to {True}.
    # This is expected; the IR nodes are still distinct (tested separately).
    result = generate(Literal[True, 1])
    assert True in result
    assert 1 in result  # always true since True == 1 in Python


# --------------------------------------------------------------------------
# Validate: arithmetic on bool references must be rejected
# --------------------------------------------------------------------------


def test_generate_rejects_arithmetic_on_bool_reference():
    """Add with a bool-typed reference must fail validation."""
    generate = core_attr("generate")
    Add = core_attr("Add")
    Eq = core_attr("Eq")
    Name = core_attr("Name")
    with pytest.raises((TypeError, ValueError)):
        generate(
            Annotated[bool, Name("X")],
            Eq(Add(ref("X"), int_const(1)), int_const(2)),
            {},
        )


def test_generate_rejects_ordering_on_bool_reference():
    """Lt with a bool-typed reference must fail validation."""
    generate = core_attr("generate")
    Lt = core_attr("Lt")
    Name = core_attr("Name")
    with pytest.raises((TypeError, ValueError)):
        generate(Annotated[bool, Name("X")], Lt(ref("X"), int_const(1)), {})


def test_generate_rejects_neg_on_any_typed_reference():
    generate = core_attr("generate")
    Eq = core_attr("Eq")
    Neg = core_attr("Neg")
    Name = core_attr("Name")
    with pytest.raises((TypeError, ValueError)):
        generate(
            Annotated[Tuple[bool], Name("X")],
            Eq(Neg(ref("X")), int_const(0)),
            {},
        )


def test_generate_rejects_arithmetic_on_any_typed_reference():
    generate = core_attr("generate")
    Add = core_attr("Add")
    Eq = core_attr("Eq")
    Name = core_attr("Name")
    with pytest.raises((TypeError, ValueError)):
        generate(
            Annotated[Tuple[bool], Name("X")],
            Eq(Add(ref("X"), int_const(1)), int_const(2)),
            {},
        )


def test_generate_rejects_ordering_on_any_typed_reference():
    generate = core_attr("generate")
    Lt = core_attr("Lt")
    Name = core_attr("Name")
    with pytest.raises((TypeError, ValueError)):
        generate(Annotated[Tuple[bool], Name("X")], Lt(ref("X"), int_const(1)), {})


# --------------------------------------------------------------------------
# Expression evaluation (direct tests on eval module)
# --------------------------------------------------------------------------


def test_eval_full_expression_basic_arithmetic():
    expr = Add(Mul(Reference("x"), IntegerConstant(3)), IntegerConstant(1))
    assert eval_expression(expr, {"x": 4}) == 13


def test_eval_partial_and_short_circuits_on_false():
    expr = And(BooleanConstant(False), Reference("y"))
    assert eval_expression_partial(expr, {}) is False


def test_eval_partial_or_short_circuits_on_true():
    expr = Or(BooleanConstant(True), Reference("y"))
    assert eval_expression_partial(expr, {}) is True


def test_eval_partial_unknown_propagates_through_arithmetic():
    expr = Add(Reference("x"), IntegerConstant(1))
    assert eval_expression_partial(expr, {}) is Unknown


def test_eval_partial_and_both_unknown():
    expr = And(Reference("x"), Reference("y"))
    assert eval_expression_partial(expr, {}) is Unknown


def test_eval_partial_neg_of_unknown():
    expr = Neg(Reference("x"))
    assert eval_expression_partial(expr, {}) is Unknown


# --------------------------------------------------------------------------
# Canonical ordering
# --------------------------------------------------------------------------


def test_canonical_order_bools_false_before_true():
    assert canonical_sorted([False, True]) == [False, True]


def test_canonical_order_ints_ascending():
    assert canonical_sorted([3, 1, 2]) == [1, 2, 3]


def test_canonical_order_strings_lexicographic():
    assert canonical_sorted(["b", "a", "c"]) == ["a", "b", "c"]


def test_canonical_order_none_before_tuples():
    result = canonical_sorted([("x",), None])
    assert result[0] is None


def test_canonical_order_tuples_lexicographic():
    data = [(True, False), (True, True), (False, True), (False, False)]
    assert canonical_sorted(data) == [(False, False), (False, True), (True, False), (True, True)]


def test_canonical_first_selects_minimum():
    assert canonical_first([False, True]) is False


# --------------------------------------------------------------------------
# Domain computation
# --------------------------------------------------------------------------


def test_domain_map_single_named_label():
    node = normalize(Annotated[bool, CoreName("X")])
    dm = domain_map(node)
    assert set(dm["X"]) == {True, False}


def test_domain_map_repeated_label_intersection():
    Name = core_attr("Name")
    tree = Tuple[Annotated[int, ValueRange(1, 5), Name("X")], Annotated[int, ValueRange(3, 7), Name("X")]]
    node = normalize(tree)
    dm = domain_map(node)
    assert set(dm["X"]) == {3, 4, 5}


def test_domain_map_repeated_label_empty_intersection():
    Name = core_attr("Name")
    tree = Tuple[Annotated[int, ValueRange(1, 2), Name("X")], Annotated[int, ValueRange(5, 6), Name("X")]]
    node = normalize(tree)
    dm = domain_map(node)
    assert dm["X"] == [], f"Expected empty domain but got {dm['X']!r}"


def test_domain_map_repeated_label_bool_int_type_aware():
    """Intersecting bool and int domains must be type-aware (True != 1 semantically).

    Without type-awareness, ``frozenset({True, False}) & frozenset({1, 2})``
    returns ``frozenset({True})`` because Python considers ``True == 1``.
    The corrected intersection must return an empty domain.
    """
    Name = core_attr("Name")
    # Bool label vs ValueRange(1, 2): True == 1 in Python but they are
    # different types, so the intersection must be empty.
    tree = Tuple[Annotated[bool, Name("X")], Annotated[int, ValueRange(1, 2), Name("X")]]
    node = normalize(tree)
    dm = domain_map(node)
    assert dm["X"] == [], f"Expected empty domain but got {dm['X']!r}"


def test_domain_map_repeated_label_tuple_bool_int_type_aware():
    """Domain intersection must be recursively type-aware for nested tuples.

    Python's ``(True,) == (1,)`` because tuple equality delegates to element
    equality, which conflates bool and int.  _type_aware_intersect must handle
    this correctly via recursive tagging.
    """
    # Simulating intersection of tuple domains where one occurrence contains
    # bool tuples and another contains int tuples of the same value.
    bool_tuples = frozenset({(True,), (False,)})
    int_tuples = frozenset({(1,), (2,)})
    result = _type_aware_intersect(bool_tuples, int_tuples)
    assert result == frozenset(), (
        f"Expected empty domain for bool-tuple vs int-tuple intersection, "
        f"but got {result!r}. Python's naive & would return {{(1,)}}."
    )


def test_domain_map_union_literal_bool_int_preserves_distinct_types():
    """domain_map must preserve both True (bool) and 1 (int) as distinct alternatives.

    Python's raw set union collapses ``True`` and ``1`` into a single element
    because ``True == 1``.  When a label's occurrence is
    ``Union[Literal[True], Literal[1]]``, the domain must preserve both typed
    alternatives so that a later type-aware intersection with ``Literal[1]``
    yields ``[1]`` (the int) rather than ``[]`` (empty).
    """
    # Occurrence 1: Union[Literal[True], Literal[1]] — should preserve both types.
    # Occurrence 2: Literal[1]  (int) — domain is {1}.
    # Expected type-aware intersection: {1 (int)} only.
    occ1_node = NamedNode("X", UnionNode((LiteralNode(True), LiteralNode(1))))
    occ2_node = NamedNode("X", LiteralNode(1))
    tree_node = TupleNode((occ1_node, occ2_node))
    dm = domain_map(tree_node)
    assert len(dm["X"]) == 1, f"Expected [1] but got {dm['X']!r}"
    assert dm["X"][0] == 1, f"Expected 1 (int) but got {dm['X'][0]!r}"
    assert type(dm["X"][0]) is int, f"Expected type int but got {type(dm['X'][0])!r}"


def test_generate_union_literal_bool_int_respects_type_identity():
    """domain_map must correctly handle union of bool/int-equal literals for a repeated label.

    This tests the integration through domain_map to verify X=1 is the only
    admissible value when one occurrence is Union[Literal[True], Literal[1]]
    and the other is Literal[1].
    """
    occ1 = NamedNode("X", UnionNode((LiteralNode(True), LiteralNode(1))))
    occ2 = NamedNode("X", LiteralNode(1))
    node = TupleNode((occ1, occ2))
    dm = domain_map(node)
    assert len(dm["X"]) == 1 and type(dm["X"][0]) is int and dm["X"][0] == 1, (
        f"Expected X domain = [1 (int)], got {dm['X']!r}"
    )


def test_structural_eq_distinguishes_bool_from_int():
    """Eq/Ne must treat True and 1 as distinct values.

    Python's ``True == 1`` would make ``Eq(Reference("X"), IntegerConstant(1))``
    hold for ``X=True``, but structural equality must reject that.
    """
    assert _structural_eq(True, True) is True
    assert _structural_eq(1, 1) is True
    assert _structural_eq(True, 1) is False
    assert _structural_eq(1, True) is False
    assert _structural_eq((True,), (1,)) is False
    assert _structural_eq((True,), (True,)) is True
    assert _structural_eq((1,), (1,)) is True


def test_eval_eq_type_aware():
    """eval_expression(Eq(...)) must use structural equality."""
    expr = Eq(Reference("X"), IntegerConstant(1))
    assert eval_expression(expr, {"X": 1}) is True
    assert eval_expression(expr, {"X": True}) is False  # True == 1 in Python, but Eq is structural


def test_eval_ne_type_aware():
    """eval_expression(Ne(...)) must use structural equality."""
    expr = Ne(Reference("X"), IntegerConstant(1))
    assert eval_expression(expr, {"X": 1}) is False
    assert eval_expression(expr, {"X": True}) is True  # True != 1 structurally


def test_generate_unnamed_false_constraint_returns_empty_denotation():
    """generate(Literal[True], BooleanExpression(False), {}) must return set().

    Without the unnamed-tree constraint check, the fast path returns {True}
    instead of set().
    """
    generate = core_attr("generate")
    BooleanExpression = core_attr("BooleanExpression")
    result = generate(Literal[True], BooleanExpression(False), {})
    assert result == set(), f"Expected set() but got {result!r}"


def test_generate_unnamed_true_constraint_returns_full_denotation():
    """generate(bool, BooleanExpression(True), {}) must return {True, False}."""
    generate = core_attr("generate")
    BooleanExpression = core_attr("BooleanExpression")
    result = generate(bool, BooleanExpression(True), {})
    assert result == {True, False}, f"Expected {{True, False}} but got {result!r}"


def test_values_bool_gives_two_values():
    values = core_attr("values")
    assert values(bool) == {True, False}


def test_values_int_range_gives_range():
    values = core_attr("values")
    assert values(Annotated[int, ValueRange(10, 12)]) == {10, 11, 12}


def test_values_none_gives_singleton():
    values = core_attr("values")
    assert values(None) == {None}


def test_values_nested_tuple():
    values = core_attr("values")
    tree = Tuple[bool, Literal["ok"]]
    assert values(tree) == {(True, "ok"), (False, "ok")}


# --------------------------------------------------------------------------
# Cache helpers
# --------------------------------------------------------------------------


def test_mentioned_labels_arithmetic_expression():
    mentioned_labels = core_attr("mentioned_labels")
    Add = core_attr("Add")
    expr = Add(ref("A"), ref("B"))
    assert mentioned_labels(expr) == {"A", "B"}


def test_mentioned_labels_constant_has_no_labels():
    mentioned_labels = core_attr("mentioned_labels")
    assert mentioned_labels(int_const(42)) == set()


def test_is_label_closed_single_label():
    node = normalize(Annotated[bool, CoreName("X")])
    assert is_label_closed(node, node) is True


def test_is_constraint_independent_disjoint_labels():
    subtree = normalize(Annotated[bool, CoreName("X")])
    constraint = Reference("Y")
    assert is_constraint_independent(subtree, constraint) is True


def test_is_constraint_independent_overlapping_labels():
    subtree = normalize(Annotated[bool, CoreName("X")])
    constraint = Reference("X")
    assert is_constraint_independent(subtree, constraint) is False


def test_is_guaranteed_cacheable_unnamed():
    node = normalize(bool)
    assert is_guaranteed_cacheable(node, node, BooleanConstant(True)) is True


def test_is_guaranteed_cacheable_label_closed_and_independent():
    node = normalize(Annotated[bool, CoreName("X")])
    constraint = Reference("Y")
    assert is_guaranteed_cacheable(node, node, constraint) is True


# --------------------------------------------------------------------------
# Nested / complex generate scenarios
# --------------------------------------------------------------------------


def test_generate_nested_two_constrained_labels():
    """Two independent named booleans can be jointly constrained."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    And = core_attr("And")
    Eq = core_attr("Eq")
    tree = Tuple[Annotated[bool, Name("A")], Annotated[bool, Name("B")]]
    constraint = And(Eq(ref("A"), bool_const(True)), Eq(ref("B"), bool_const(False)))
    assert generate(tree, constraint, {}) == {(True, False)}


def test_generate_union_label_with_equality_constraint():
    """Constraint on a union-typed named label narrows to matching values."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    tree = Annotated[Union[Literal[1], Literal[2], Literal[3]], Name("X")]
    constraint = Eq(ref("X"), int_const(2))
    assert generate(tree, constraint, {}) == {2}


def test_generate_three_label_strict_ordering():
    """A < B < C constraint over three integer labels."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    And = core_attr("And")
    Gt = core_attr("Gt")
    tree = Tuple[
        Annotated[int, ValueRange(0, 2), Name("A")],
        Annotated[int, ValueRange(0, 2), Name("B")],
        Annotated[int, ValueRange(0, 2), Name("C")],
    ]
    constraint = And(Gt(ref("B"), ref("A")), Gt(ref("C"), ref("B")))
    assert generate(tree, constraint, {}) == {(0, 1, 2)}


def test_generate_none_in_named_union():
    """Named label with a union that includes None."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Annotated[Union[None, Literal["x"]], Name("V")]
    assert generate(tree, true_expr(), {}) == {None, "x"}


def test_generate_le_and_ge_constraints():
    """Le and Ge operators filter an integer range correctly."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    And = core_attr("And")
    Le = core_attr("Le")
    Ge = core_attr("Ge")
    tree = Annotated[int, ValueRange(0, 5), Name("X")]
    constraint = And(Ge(ref("X"), int_const(2)), Le(ref("X"), int_const(4)))
    assert generate(tree, constraint, {}) == {2, 3, 4}


def test_generate_arbitrary_is_stable_across_calls():
    """Repeated arbitrary calls always return the same value."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Annotated[int, ValueRange(0, 10), Name("N")]
    r1 = generate(tree, true_expr(), {"N": "arbitrary"})
    r2 = generate(tree, true_expr(), {"N": "arbitrary"})
    assert r1 == r2
    assert len(r1) == 1


def test_apply_methods_arbitrary_uses_type_aware_filtering() -> None:
    assignments: list[dict[str, object]] = [{"X": True}, {"X": 1}]
    reduced = apply_methods(assignments, {"X": "arbitrary"})
    assert reduced == [{"X": True}]


def test_generate_non_empty_for_all_super_methods_when_satisfiable():
    """All super methods produce a non-empty result when the problem is satisfiable."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Annotated[int, ValueRange(1, 5), Name("X")]
    for method in ["all", "arbitrary", "uniform_random"]:
        result = generate(tree, true_expr(), {"X": method})
        assert result, f"Expected non-empty result for method={method!r}"


# --------------------------------------------------------------------------
# Normalize: Literal value type restrictions
# --------------------------------------------------------------------------


def test_normalize_rejects_float_literal():
    """Literal with a float value must be rejected (not in supported types)."""
    generate = core_attr("generate")
    with pytest.raises(ValueError):
        generate(Literal[1.5])


def test_normalize_rejects_bytes_literal():
    """Literal with a bytes value must be rejected (not in supported types)."""
    generate = core_attr("generate")
    with pytest.raises(ValueError):
        generate(Literal[b"x"])


def test_normalize_accepts_none_literal():
    """Literal[None] must be accepted as a singleton domain."""
    generate = core_attr("generate")
    assert generate(Literal[None]) == {None}


def test_normalize_accepts_all_supported_scalar_literals():
    """Literal with mixed supported scalar types must be accepted."""
    generate = core_attr("generate")
    assert generate(Literal[True, 0, "hi"]) == {True, 0, "hi"}


# --------------------------------------------------------------------------
# Validate: validate_methods type guard
# --------------------------------------------------------------------------


def test_validate_methods_rejects_non_mapping():
    """Passing a list (not a Mapping) as methods must raise TypeError."""
    tree = normalize(bool)
    with pytest.raises(TypeError):
        validate_methods(tree, ["all"])  # type: ignore[arg-type]


def test_validate_methods_rejects_tuple_as_methods():
    """Passing a tuple as methods must raise TypeError."""
    tree = normalize(bool)
    with pytest.raises(TypeError):
        validate_methods(tree, ("all",))  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Search: domain precomputation does not change results
# --------------------------------------------------------------------------


def test_search_sorted_domain_precomputation_produces_correct_results():
    """Results from search() must be the same whether domains are pre-sorted or not."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    tree = Annotated[int, ValueRange(0, 4), Name("X")]
    constraint = Eq(ref("X"), int_const(3))
    assert generate(tree, constraint, {}) == {3}


# --------------------------------------------------------------------------
# Validate: nested NamedNode rejection
# --------------------------------------------------------------------------


def test_validate_rejects_nested_named_node():
    """A NamedNode whose inner is also a NamedNode must be rejected."""
    with pytest.raises(ValueError, match="[Nn]ested"):
        validate_tree(NamedNode("outer", NamedNode("inner", BoolNode())))


def test_generate_rejects_nested_name_annotations():
    """Annotated[Annotated[bool, Name("inner")], Name("outer")] must be rejected."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    # normalize() builds NamedNode("outer", NamedNode("inner", BoolNode())).
    # validate_tree() then raises ValueError because the inner subtree contains a Name.
    inner = Annotated[bool, Name("inner")]
    outer = Annotated[inner, Name("outer")]
    with pytest.raises(ValueError):
        generate(outer, true_expr(), {})


def test_validate_rejects_deeply_nested_named_node():
    """A NamedNode whose inner subtree contains a NamedNode at any depth must be rejected."""
    # NamedNode("outer", TupleNode([NamedNode("inner", BoolNode())])) — Name inside a Tuple inside a Name
    with pytest.raises(ValueError, match="[Nn]ested"):
        validate_tree(NamedNode("outer", TupleNode((NamedNode("inner", BoolNode()),))))


# -------------------------------------------------------------------------
# Interesting examples
# -------------------------------------------------------------------------


def test_example12():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Gt = core_attr("Gt")
    tree = Tuple[Annotated[int, ValueRange(0, 9), Name("X")], Annotated[int, ValueRange(0, 9), Name("Y")]]
    constraint = Gt(ref("X"), ref("Y"))
    with random_seed(7):
        assert generate(tree, constraint, {"Y": "uniform_random", "X": "all"}) == {
            (5, 4),
            (6, 4),
            (7, 4),
            (8, 4),
            (9, 4),
        }


def test_example11():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Gt = core_attr("Gt")
    tree = Tuple[Annotated[int, ValueRange(0, 9), Name("X")], Annotated[int, ValueRange(0, 9), Name("Y")]]
    constraint = Gt(ref("X"), ref("Y"))
    with random_seed(7):
        assert generate(tree, constraint, {"X": "all", "Y": "uniform_random"}) == {
            (5, 4),
            (6, 4),
            (7, 4),
            (8, 4),
            (9, 4),
        }


def test_example10():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Gt = core_attr("Gt")
    tree = Tuple[Annotated[int, ValueRange(0, 99), Name("X")], Annotated[int, ValueRange(0, 99), Name("Y")]]
    constraint = Gt(ref("X"), ref("Y"))
    with random_seed(42):
        assert generate(tree, constraint, {"X": "uniform_random", "Y": "uniform_random"}) == {(80, 2)}


def test_example9():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Gt = core_attr("Gt")
    tree = Tuple[Annotated[int, ValueRange(0, 2), Name("X")], Annotated[int, ValueRange(0, 2), Name("Y")]]
    constraint = Gt(ref("X"), ref("Y"))
    assert generate(tree, constraint, {"X": "arbitrary"}) == {(1, 0)}


def test_example8():
    generate = core_attr("generate")
    tree = Union[Annotated[int, ValueRange(1, 3)], Literal[True, False]]
    assert generate(tree) == {False, True, 1, 2, 3}


def test_example7():
    generate = core_attr("generate")
    tree = Union[Annotated[int, ValueRange(0, 3)], Literal[True, False]]
    assert generate(tree) == {False, 1, 2, 3}


def test_example6():
    generate = core_attr("generate")
    tree = Union[Annotated[int, ValueRange(1, 3)], bool]
    assert generate(tree) == {False, True, 1, 2, 3}


def test_example5():
    generate = core_attr("generate")
    tree = Union[Annotated[int, ValueRange(3, 5)], bool]
    assert generate(tree) == {3, 4, 5, True, False}


def test_example4():
    generate = core_attr("generate")
    tree = bool
    assert generate(tree) == {False, True}


def test_example3():
    generate = core_attr("generate")
    tree = Union[Annotated[int, ValueRange(0, 2)], bool]
    assert generate(tree) == {0, 1, 2, False, True}


def test_example2():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Gt = core_attr("Gt")
    tree = Tuple[Annotated[int, ValueRange(0, 2), Name("X")], Annotated[int, ValueRange(0, 2), Name("Y")]]
    constraint = Gt(ref("X"), ref("Y"))
    assert generate(tree, constraint, {}) == {(1, 0), (2, 0), (2, 1)}
