from __future__ import annotations

import importlib
import random
from itertools import combinations_with_replacement, permutations
from typing import Annotated, Any, Literal, Tuple, Union, cast

import pytest

from equivalib.core.cache import is_constraint_independent, is_guaranteed_cacheable, is_label_closed
from equivalib.core.domains import _type_aware_intersect, domain_map
from equivalib.core.eval import Unknown, _structural_eq, eval_expression, eval_expression_partial
from equivalib.core.expression import (
    Add,
    And,
    BooleanConstant,
    Eq,
    FloorDiv,
    Ge,
    Gt,
    IntegerConstant,
    Le,
    Lt,
    Mod,
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
from equivalib.core.sat import sat_search as _sat_search
from equivalib.core.types import BoolNode, IntRangeNode, LiteralNode, NamedNode, TupleNode, UnionNode, labels_in_order
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


def _int_bounds(label: str, lo: int, hi: int) -> Any:
    """Return a bounds constraint for a named int label: lo <= label <= hi."""
    return And(Ge(ref(label), int_const(lo)), Le(ref(label), int_const(hi)))


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


def test_generate_bounded_int_literal():
    generate = core_attr("generate")
    assert generate(Literal[3, 4], true_expr(), {}) == {3, 4}


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


def test_generate_named_int_range_from_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Annotated[int, Name("X")]
    constraint = And(Ge(ref("X"), int_const(1)), Le(ref("X"), int_const(2)))
    assert generate(tree, constraint, {}) == {1, 2}


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
    tree = Tuple[Annotated[int, Name("X")], Annotated[int, Name("X")]]
    constraint = And(Ge(ref("X"), int_const(3)), Le(ref("X"), int_const(5)))
    assert generate(tree, constraint, {"X": "all"}) == {(3, 3), (4, 4), (5, 5)}


def test_generate_empty_when_repeated_label_domains_do_not_overlap():
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[Annotated[int, Name("X")], Annotated[int, Name("X")]]
    constraint = And(Ge(ref("X"), int_const(5)), Le(ref("X"), int_const(2)))
    assert generate(tree, constraint, {}) == set()


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
    tree = Tuple[Annotated[int, Name("X")], Annotated[int, Name("Y")]]
    constraint = And(
        And(_int_bounds("X", 0, 3), _int_bounds("Y", 0, 3)),
        And(Gt(ref("X"), int_const(0)), Lt(ref("X"), ref("Y")))
    )
    assert generate(tree, constraint, {"X": "all", "Y": "all"}) == {(1, 2), (1, 3), (2, 3)}


def test_generate_with_add_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Add = core_attr("Add")
    Eq = core_attr("Eq")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", 0, 4), Eq(Add(ref("X"), int_const(1)), int_const(3)))
    assert generate(tree, constraint, {"X": "all"}) == {2}


def test_generate_with_sub_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Sub = core_attr("Sub")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", 0, 4), Eq(Sub(ref("X"), int_const(1)), int_const(1)))
    assert generate(tree, constraint, {"X": "all"}) == {2}


def test_generate_with_mul_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Mul = core_attr("Mul")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", 0, 4), Eq(Mul(ref("X"), int_const(2)), int_const(4)))
    assert generate(tree, constraint, {"X": "all"}) == {2}


def test_generate_with_floor_div_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    FloorDiv = core_attr("FloorDiv")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", 0, 5), Eq(FloorDiv(ref("X"), int_const(2)), int_const(1)))
    assert generate(tree, constraint, {"X": "all"}) == {2, 3}


def test_generate_with_mod_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Mod = core_attr("Mod")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", 0, 5), Eq(Mod(ref("X"), int_const(2)), int_const(1)))
    assert generate(tree, constraint, {"X": "all"}) == {1, 3, 5}


def test_generate_with_neg_constraint():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Neg = core_attr("Neg")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", 0, 4), Eq(Neg(ref("X")), int_const(-2)))
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
    tree = Tuple[Union[Literal["blue"], Literal["red"]], Literal[1, 2]]
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


def test_generate_rejects_named_int_without_bounds():
    generate = core_attr("generate")
    Name = core_attr("Name")
    with pytest.raises(ValueError):
        generate(Annotated[int, Name("X")], true_expr(), {})


def test_generate_rejects_plain_int_in_core():
    generate = core_attr("generate")
    with pytest.raises(ValueError):
        generate(int, true_expr(), {})


def test_generate_rejects_duplicate_name_metadata():
    generate = core_attr("generate")
    Name = core_attr("Name")
    with pytest.raises(ValueError):
        generate(Annotated[bool, Name("X"), Name("Y")], true_expr(), {})


def test_generate_rejects_unknown_int_metadata():
    generate = core_attr("generate")
    with pytest.raises(ValueError):
        generate(Annotated[int, "some_metadata"], true_expr(), {})


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
        generate(Annotated[int, Name("X")], Add(ref("X"), int_const(1)), {"X": "all"})


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
    """Unnamed Literal expands fully for every named assignment."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[Literal[0, 1], Annotated[bool, Name("X")]]
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


def test_generate_named_int_range_from_constraint_alternate():
    """Named int with bounds from constraint."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Annotated[int, Name("X")]
    constraint = And(Ge(ref("X"), int_const(5)), Le(ref("X"), int_const(7)))
    assert generate(tree, constraint, {}) == {5, 6, 7}


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
    node = TupleNode((NamedNode("X", IntRangeNode(1, 5)), NamedNode("X", IntRangeNode(3, 7))))
    dm = domain_map(node)
    assert set(dm["X"]) == {3, 4, 5}


def test_domain_map_repeated_label_empty_intersection():
    node = TupleNode((NamedNode("X", IntRangeNode(1, 2)), NamedNode("X", IntRangeNode(5, 6))))
    dm = domain_map(node)
    assert dm["X"] == [], f"Expected empty domain but got {dm['X']!r}"


def test_domain_map_repeated_label_bool_int_type_aware():
    """Intersecting bool and int domains must be type-aware (True != 1 semantically).

    Without type-awareness, ``frozenset({True, False}) & frozenset({1, 2})``
    returns ``frozenset({True})`` because Python considers ``True == 1``.
    The corrected intersection must return an empty domain.
    """
    # Bool label vs IntRangeNode(1, 2): True == 1 in Python but they are
    # different types, so the intersection must be empty.
    node = TupleNode((NamedNode("X", BoolNode()), NamedNode("X", IntRangeNode(1, 2))))
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
    assert values(Literal[10, 11, 12]) == {10, 11, 12}


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
    tree = Tuple[Annotated[int, Name("A")], Annotated[int, Name("B")], Annotated[int, Name("C")]]
    constraint = And(
        And(_int_bounds("A", 0, 2), And(_int_bounds("B", 0, 2), _int_bounds("C", 0, 2))),
        And(Gt(ref("B"), ref("A")), Gt(ref("C"), ref("B")))
    )
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
    tree = Annotated[int, Name("X")]
    constraint = And(And(Ge(ref("X"), int_const(0)), Le(ref("X"), int_const(5))),
                     And(Ge(ref("X"), int_const(2)), Le(ref("X"), int_const(4))))
    assert generate(tree, constraint, {}) == {2, 3, 4}


def test_generate_arbitrary_is_stable_across_calls():
    """Repeated arbitrary calls always return the same value."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Annotated[int, Name("N")]
    constraint = And(Ge(ref("N"), int_const(0)), Le(ref("N"), int_const(10)))
    r1 = generate(tree, constraint, {"N": "arbitrary"})
    r2 = generate(tree, constraint, {"N": "arbitrary"})
    assert r1 == r2
    assert len(r1) == 1


def test_apply_methods_arbitrary_uses_type_aware_filtering() -> None:
    assignments: list[dict[str, object]] = [{"X": True}, {"X": 1}]
    reduced = apply_methods(assignments, {"X": "arbitrary"}, ["X"])
    assert reduced == [{"X": True}]


# --------------------------------------------------------------------------
# Alpha conversion: renaming labels consistently must not change the output
# --------------------------------------------------------------------------


def test_alpha_conversion_arbitrary_single_label_is_invariant():
    """Renaming the only label does not change the result for 'arbitrary'."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    result_x = generate(Annotated[bool, Name("X")], true_expr(), {"X": "arbitrary"})
    result_y = generate(Annotated[bool, Name("Y")], true_expr(), {"Y": "arbitrary"})
    assert result_x == result_y


def test_alpha_conversion_arbitrary_two_labels_different_names_same_output():
    """Consistently renaming both labels in a constrained tuple gives the same output."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Ne = core_attr("Ne")

    # Original: X first, Y second in tree, constraint, and methods.
    tree_xy = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    constraint_xy = Ne(ref("X"), ref("Y"))
    result_xy = generate(tree_xy, constraint_xy, {"X": "arbitrary", "Y": "arbitrary"})

    # Alpha conversion: rename X -> "B" (second alpha), Y -> "A" (first alpha).
    # The structural order of labels in the tree now has "B" before "A",
    # which mirrors the original ordering of X before Y.
    tree_ba = Tuple[Annotated[bool, Name("B")], Annotated[bool, Name("A")]]
    constraint_ba = Ne(ref("B"), ref("A"))
    result_ba = generate(tree_ba, constraint_ba, {"B": "arbitrary", "A": "arbitrary"})

    assert result_xy == result_ba


def test_alpha_conversion_mixed_methods_preserved_under_renaming():
    """'all' + 'arbitrary' result is invariant under consistent label renaming."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Ne = core_attr("Ne")

    # Original: X uses "all", Y uses "arbitrary".
    tree_xy = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    constraint_xy = Ne(ref("X"), ref("Y"))
    result_xy = generate(tree_xy, constraint_xy, {"X": "all", "Y": "arbitrary"})

    # Alpha conversion: X -> "B", Y -> "A" (structural order preserved: B before A).
    tree_ba = Tuple[Annotated[bool, Name("B")], Annotated[bool, Name("A")]]
    constraint_ba = Ne(ref("B"), ref("A"))
    result_ba = generate(tree_ba, constraint_ba, {"B": "all", "A": "arbitrary"})

    assert result_xy == result_ba


def test_generate_non_empty_for_all_super_methods_when_satisfiable():
    """All super methods produce a non-empty result when the problem is satisfiable."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Annotated[int, Name("X")]
    constraint = And(Ge(ref("X"), int_const(1)), Le(ref("X"), int_const(5)))
    for method in ["all", "arbitrary", "uniform_random"]:
        result = generate(tree, constraint, {"X": method})
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
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", 0, 4), Eq(ref("X"), int_const(3)))
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
# Interesting example helpers
# -------------------------------------------------------------------------


_INTERVAL_RELATION_TOUCH = 0
_INTERVAL_RELATION_KISS = 1
_INTERVAL_RELATION_OVERLAP = 2
_INTERVAL_RELATION_DISJOINT = 3
_ONE = IntegerConstant(1)


def _and_all(*expressions: Any) -> Any:
    result: Any = BooleanConstant(True)
    for expression in expressions:
        result = And(result, expression)
    return result


def _or_all(*expressions: Any) -> Any:
    result: Any = BooleanConstant(False)
    for expression in expressions:
        result = Or(result, expression)
    return result


def _named_int_type(label: str, coordinate_max: int) -> Any:
    return Annotated[int, CoreName(label)]


def _int_range_bounds_constraint(labels: list[str], lo: int, hi: int) -> Any:
    """Return And of Ge/Le bounds for each label in labels."""
    result: Any = BooleanConstant(True)
    for label in labels:
        result = And(result, And(Ge(ref(label), IntegerConstant(lo)), Le(ref(label), IntegerConstant(hi))))
    return result


def _named_interval_type(prefix: str, coordinate_max: int) -> Any:
    return Tuple[
        _named_int_type(f"{prefix}0", coordinate_max),
        _named_int_type(f"{prefix}1", coordinate_max),
    ]


def _interval_tree(count: int, coordinate_max: int = 99) -> Any:
    if count == 0:
        return Tuple[()]
    if count == 1:
        return Tuple[_named_interval_type("A", coordinate_max)]
    if count == 2:
        return Tuple[
            _named_interval_type("A", coordinate_max),
            _named_interval_type("B", coordinate_max),
        ]
    if count == 3:
        return Tuple[
            _named_interval_type("A", coordinate_max),
            _named_interval_type("B", coordinate_max),
            _named_interval_type("C", coordinate_max),
        ]
    raise ValueError(f"Unsupported interval count: {count!r}")


def _integer_tree(count: int, coordinate_max: int = 99) -> Any:
    if count == 0:
        return Tuple[()]
    if count == 1:
        return Tuple[_named_int_type("A", coordinate_max)]
    if count == 2:
        return Tuple[
            _named_int_type("A", coordinate_max),
            _named_int_type("B", coordinate_max),
        ]
    if count == 3:
        return Tuple[
            _named_int_type("A", coordinate_max),
            _named_int_type("B", coordinate_max),
            _named_int_type("C", coordinate_max),
        ]
    if count == 4:
        return Tuple[
            _named_int_type("A", coordinate_max),
            _named_int_type("B", coordinate_max),
            _named_int_type("C", coordinate_max),
            _named_int_type("D", coordinate_max),
        ]
    raise ValueError(f"Unsupported integer count: {count!r}")


def _interval_is_valid(prefix: str) -> Any:
    return Le(ref(f"{prefix}0"), ref(f"{prefix}1"))


def _interval_relation_expr(left: str, right: str, relation: int) -> Any:
    left_start = ref(f"{left}0")
    left_end = ref(f"{left}1")
    right_start = ref(f"{right}0")
    right_end = ref(f"{right}1")

    if relation == _INTERVAL_RELATION_TOUCH:
        return _or_all(Eq(left_end, right_start), Eq(right_end, left_start))
    if relation == _INTERVAL_RELATION_KISS:
        return _or_all(
            Eq(Add(left_end, _ONE), right_start),
            Eq(Add(right_end, _ONE), left_start),
        )
    if relation == _INTERVAL_RELATION_OVERLAP:
        return _and_all(Lt(left_start, right_end), Lt(right_start, left_end))
    if relation == _INTERVAL_RELATION_DISJOINT:
        return _or_all(
            Lt(Add(left_end, _ONE), right_start),
            Lt(Add(right_end, _ONE), left_start),
        )
    raise ValueError(f"Unknown interval relation: {relation!r}")


def _interval_signature_constraint(signature: tuple[int, tuple[int, ...]]) -> Any:
    count, relations = signature
    labels = "ABC"[:count]
    pieces = [_interval_is_valid(label) for label in labels]

    relation_index = 0
    for left_index in range(count):
        for right_index in range(left_index + 1, count):
            pieces.append(
                _interval_relation_expr(
                    labels[left_index],
                    labels[right_index],
                    relations[relation_index],
                )
            )
            relation_index += 1

    return _and_all(*pieces)


def _interval_relation_code(
    left: tuple[int, int],
    right: tuple[int, int],
) -> int:
    left_start, left_end = left
    right_start, right_end = right

    if left_end + 1 < right_start or right_end + 1 < left_start:
        return _INTERVAL_RELATION_DISJOINT
    if left_end + 1 == right_start or right_end + 1 == left_start:
        return _INTERVAL_RELATION_KISS
    if left_end == right_start or right_end == left_start:
        return _INTERVAL_RELATION_TOUCH
    if left_start < right_end and right_start < left_end:
        return _INTERVAL_RELATION_OVERLAP
    raise AssertionError((left, right))


def _canonical_interval_relation_signature(
    intervals: tuple[tuple[int, int], ...],
) -> tuple[int, tuple[int, ...]]:
    count = len(intervals)
    best: tuple[int, ...] | None = None

    for order in permutations(range(count)):
        candidate = tuple(
            _interval_relation_code(intervals[order[left_index]], intervals[order[right_index]])
            for left_index in range(count)
            for right_index in range(left_index + 1, count)
        )
        if best is None or candidate < best:
            best = candidate

    return count, best or ()


def _independent_interval_relation_signatures(
    reduced_coordinate_max: int = 10,
) -> set[tuple[int, tuple[int, ...]]]:
    intervals = [
        (start, end) for start in range(reduced_coordinate_max + 1) for end in range(start, reduced_coordinate_max + 1)
    ]
    signatures: set[tuple[int, tuple[int, ...]]] = set()

    for count in range(4):
        signatures.update(
            _canonical_interval_relation_signature(interval_tuple)
            for interval_tuple in combinations_with_replacement(intervals, count)
        )

    return signatures


def _generate_interval_relation_representative(
    signature: tuple[int, tuple[int, ...]],
) -> tuple[tuple[int, int], ...]:
    generate = core_attr("generate")
    count, _ = signature
    labels = [f"{label}{endpoint}" for label in "ABC"[:count] for endpoint in (0, 1)]
    methods = {label: "arbitrary" for label in labels}
    bounds_constraint = _int_range_bounds_constraint(labels, 0, 99)
    full_constraint = And(bounds_constraint, _interval_signature_constraint(signature))
    result = generate(_interval_tree(count), full_constraint, methods)
    assert len(result) == 1
    representative = next(iter(result))
    assert _canonical_interval_relation_signature(representative) == signature
    return cast("tuple[tuple[int, int], ...]", representative)


def _canonical_integer_equality_signature(
    values: tuple[int, ...],
) -> tuple[int, tuple[int, ...]]:
    count = len(values)
    best: tuple[int, ...] | None = None

    for order in permutations(range(count)):
        candidate = tuple(
            0 if values[order[left_index]] == values[order[right_index]] else 1
            for left_index in range(count)
            for right_index in range(left_index + 1, count)
        )
        if best is None or candidate < best:
            best = candidate

    return count, best or ()


def _independent_integer_equality_signatures(
    reduced_coordinate_max: int = 4,
    max_count: int = 4,
) -> set[tuple[int, tuple[int, ...]]]:
    values = list(range(reduced_coordinate_max + 1))
    signatures: set[tuple[int, tuple[int, ...]]] = set()

    for count in range(max_count + 1):
        signatures.update(
            _canonical_integer_equality_signature(value_tuple)
            for value_tuple in combinations_with_replacement(values, count)
        )

    return signatures


def _integer_equality_signature_constraint(signature: tuple[int, tuple[int, ...]]) -> Any:
    count, equalities = signature
    labels = "ABCD"[:count]
    pieces: list[Union[Eq, Ne]] = []

    equality_index = 0
    for left_index in range(count):
        for right_index in range(left_index + 1, count):
            if equalities[equality_index] == 0:
                pieces.append(Eq(ref(labels[left_index]), ref(labels[right_index])))
            else:
                pieces.append(Ne(ref(labels[left_index]), ref(labels[right_index])))
            equality_index += 1

    return _and_all(*pieces)


def _generate_integer_equality_representative(
    signature: tuple[int, tuple[int, ...]],
) -> tuple[int, ...]:
    generate = core_attr("generate")
    count, _ = signature
    int_labels = list("ABCD"[:count])
    methods = {label: "arbitrary" for label in int_labels}
    bounds_constraint = _int_range_bounds_constraint(int_labels, 0, 99)
    full_constraint = And(bounds_constraint, _integer_equality_signature_constraint(signature))
    result = generate(_integer_tree(count), full_constraint, methods)
    assert len(result) == 1
    representative = next(iter(result))
    assert _canonical_integer_equality_signature(representative) == signature
    return cast("tuple[int, ...]", representative)


# -------------------------------------------------------------------------
# Interesting examples
# -------------------------------------------------------------------------


def test_generate_arbitrary_interval_relation_class_representatives_up_to_three_intervals():
    expected_signatures = _independent_interval_relation_signatures()
    assert len(expected_signatures) == 25

    representatives = {
        _generate_interval_relation_representative(signature) for signature in sorted(expected_signatures)
    }

    assert len(representatives) == len(expected_signatures)
    assert {
        _canonical_interval_relation_signature(representative) for representative in representatives
    } == expected_signatures


def test_generate_arbitrary_integer_equality_class_representatives_up_to_four_values():
    expected_signatures = _independent_integer_equality_signatures()
    assert len(expected_signatures) == 12

    representatives = {
        _generate_integer_equality_representative(signature) for signature in sorted(expected_signatures)
    }

    assert len(representatives) == len(expected_signatures)
    assert {
        _canonical_integer_equality_signature(representative) for representative in representatives
    } == expected_signatures


def test_example13():
    generate = core_attr("generate")
    Name = core_attr("Name")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[Union[Literal["a"], Literal["b"]], Name("E")]]
    constraint = BooleanConstant(True)
    assert generate(tree, constraint, {"X": "arbitrary", "E": "arbitrary"}) == {
        (False, "a"),
    }


def test_example12():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Gt = core_attr("Gt")
    tree = Tuple[Annotated[int, Name("X")], Annotated[int, Name("Y")]]
    constraint = And(And(_int_bounds("X", 0, 9), _int_bounds("Y", 0, 9)), Gt(ref("X"), ref("Y")))
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
    tree = Tuple[Annotated[int, Name("X")], Annotated[int, Name("Y")]]
    constraint = And(And(_int_bounds("X", 0, 9), _int_bounds("Y", 0, 9)), Gt(ref("X"), ref("Y")))
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
    tree = Tuple[Annotated[int, Name("X")], Annotated[int, Name("Y")]]
    constraint = And(And(_int_bounds("X", 0, 99), _int_bounds("Y", 0, 99)), Gt(ref("X"), ref("Y")))
    with random_seed(42):
        assert generate(tree, constraint, {"X": "uniform_random", "Y": "uniform_random"}) == {(80, 2)}


def test_example9():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Gt = core_attr("Gt")
    tree = Tuple[Annotated[int, Name("X")], Annotated[int, Name("Y")]]
    constraint = And(And(_int_bounds("X", 0, 2), _int_bounds("Y", 0, 2)), Gt(ref("X"), ref("Y")))
    assert generate(tree, constraint, {"X": "arbitrary"}) == {(1, 0)}


def test_example8():
    generate = core_attr("generate")
    tree = Union[Literal[1, 2, 3], Literal[True, False]]
    assert generate(tree) == {False, True, 1, 2, 3}


def test_example7():
    generate = core_attr("generate")
    tree = Union[Literal[0, 1, 2, 3], Literal[True, False]]
    assert generate(tree) == {False, 1, 2, 3}


def test_example6():
    generate = core_attr("generate")
    tree = Union[Literal[1, 2, 3], bool]
    assert generate(tree) == {False, True, 1, 2, 3}


def test_example5():
    generate = core_attr("generate")
    tree = Union[Literal[3, 4, 5], bool]
    assert generate(tree) == {3, 4, 5, True, False}


def test_example4():
    generate = core_attr("generate")
    tree = bool
    assert generate(tree) == {False, True}


def test_example3():
    generate = core_attr("generate")
    tree = Union[Literal[0, 1, 2], bool]
    assert generate(tree) == {0, 1, 2, False, True}


def test_example2():
    generate = core_attr("generate")
    Name = core_attr("Name")
    Gt = core_attr("Gt")
    tree = Tuple[Annotated[int, Name("X")], Annotated[int, Name("Y")]]
    constraint = And(And(_int_bounds("X", 0, 2), _int_bounds("Y", 0, 2)), Gt(ref("X"), ref("Y")))
    assert generate(tree, constraint, {}) == {(1, 0), (2, 0), (2, 1)}


# ==========================================================================
# SAT backend regression tests
# ==========================================================================

# --------------------------------------------------------------------------
# P1: Boolean Reference as a constraint
# --------------------------------------------------------------------------


def test_bool_reference_as_constraint_direct():
    """Reference("X") used directly as constraint must work (P1 regression)."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    # Constraint is just ref("X") — must select X=True assignments only.
    result = generate(Annotated[bool, Name("X")], ref("X"), {})
    assert result == {True}


def test_bool_reference_in_and_constraint():
    """And(ref("X"), ref("Y")) must filter to X=True and Y=True."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    And = core_attr("And")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    constraint = And(ref("X"), ref("Y"))
    assert generate(tree, constraint, {}) == {(True, True)}


def test_bool_reference_in_or_constraint():
    """Or(ref("X"), ref("Y")) must filter to assignments where X or Y is True."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Or = core_attr("Or")
    tree = Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
    constraint = Or(ref("X"), ref("Y"))
    result = generate(tree, constraint, {})
    assert result == {(True, True), (True, False), (False, True)}


# --------------------------------------------------------------------------
# P2: Modulo bounds for negative divisors
# --------------------------------------------------------------------------


def test_mod_with_negative_constant_divisor():
    """Mod with a negative constant divisor must produce correct results.

    Uses a Literal-union tree so the label is enumerated via Python (not
    encoded as a CP-SAT variable).  This exercises the Python constant-fold
    path ``lv % rv`` which handles negative divisors correctly.
    """
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Mod = core_attr("Mod")
    # Use a Literal union so X is an enum label (Python eval, not CP-SAT).
    tree = Annotated[
        Union[
            Literal[-3],
            Literal[-2],
            Literal[-1],
            Literal[0],
            Literal[1],
            Literal[2],
            Literal[3],
        ],
        Name("X"),
    ]
    constraint = Eq(Mod(ref("X"), int_const(-3)), int_const(-1))
    result = generate(tree, constraint, {})
    expected = {v for v in range(-3, 4) if v % -3 == -1}
    assert result == expected, f"Expected {expected}, got {result}"


def test_mod_bounds_do_not_exclude_negative_remainders():
    """Mod bounds computation must include negative remainders for negative divisors.

    Uses a Literal-union tree so the label is enumerated via Python (not
    encoded as a CP-SAT variable), ensuring Python floor-mod semantics apply.
    """
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Mod = core_attr("Mod")
    # Literal union: X is an enum label; Python % applies (handles negative divisor).
    tree = Annotated[
        Union[
            Literal[-5],
            Literal[-4],
            Literal[-3],
            Literal[-2],
            Literal[-1],
            Literal[0],
            Literal[1],
            Literal[2],
            Literal[3],
            Literal[4],
            Literal[5],
        ],
        Name("X"),
    ]
    constraint = Eq(Mod(ref("X"), int_const(-5)), int_const(-2))
    result = generate(tree, constraint, {})
    expected = {v for v in range(-5, 6) if v % -5 == -2}
    assert result == expected, f"Expected {expected}, got {result}"


# --------------------------------------------------------------------------
# Zero-divisor handling: division / modulo by constant zero
# --------------------------------------------------------------------------


def test_floordiv_by_zero_constant_yields_empty():
    """FloorDiv with a constant zero divisor must yield no solutions."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    FloorDiv = core_attr("FloorDiv")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", 0, 3), Eq(FloorDiv(ref("X"), int_const(0)), int_const(1)))
    assert generate(tree, constraint, {}) == set()


def test_mod_by_zero_constant_yields_empty():
    """Mod with a constant zero divisor must yield no solutions."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Mod = core_attr("Mod")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", 0, 3), Eq(Mod(ref("X"), int_const(0)), int_const(1)))
    assert generate(tree, constraint, {}) == set()


# --------------------------------------------------------------------------
# P1: Python floor-division and modulo semantics for SAT-encoded labels
# --------------------------------------------------------------------------
# These tests use SAT-encoded integer labels with bounds constraints.
# The constraint is evaluated via the CP-SAT model, so semantics must match
# Python's floor division // and floor modulo % (not C-style truncation).


def test_floordiv_python_semantics_negative_dividend():
    """FloorDiv must use Python // semantics (floor toward -inf), not truncated.

    Python: -1 // 2 = -1 (floor), but CP-SAT trunc: -1 / 2 = 0.
    """
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    FloorDiv = core_attr("FloorDiv")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", -3, 3), Eq(FloorDiv(ref("X"), int_const(2)), int_const(-1)))
    result = generate(tree, constraint, {})
    expected = {v for v in range(-3, 4) if v // 2 == -1}
    assert result == expected, f"Expected {expected}, got {result}"


def test_floordiv_python_semantics_negative_divisor():
    """FloorDiv with negative constant divisor must use Python // semantics."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    FloorDiv = core_attr("FloorDiv")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", -3, 3), Eq(FloorDiv(ref("X"), int_const(-2)), int_const(0)))
    result = generate(tree, constraint, {})
    expected = {v for v in range(-3, 4) if v // -2 == 0}
    assert result == expected, f"Expected {expected}, got {result}"


def test_mod_python_semantics_negative_dividend():
    """Mod with positive divisor and negative SAT-encoded dividend must use Python % semantics.

    Python: -1 % 3 = 2, but CP-SAT truncated: -1 % 3 = -1.
    """
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Mod = core_attr("Mod")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", -3, 3), Eq(Mod(ref("X"), int_const(3)), int_const(2)))
    result = generate(tree, constraint, {})
    expected = {v for v in range(-3, 4) if v % 3 == 2}
    assert result == expected, f"Expected {expected}, got {result}"


def test_mod_python_semantics_negative_dividend_positive_divisor():
    """Mod must use Python % semantics for negative dividend and positive divisor."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Mod = core_attr("Mod")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", -4, 4), Eq(Mod(ref("X"), int_const(3)), int_const(1)))
    result = generate(tree, constraint, {})
    expected = {v for v in range(-4, 5) if v % 3 == 1}
    assert result == expected, f"Expected {expected}, got {result}"


# --------------------------------------------------------------------------
# P1: FloorDiv bounds for negative dividends
# --------------------------------------------------------------------------


def test_floordiv_bounds_negative_dividend_variable_divisor():
    """FloorDiv bound computation must not invert when dividend is negative.

    l in [-5,-3], r in [2,3]: the quotient -3 (= -5//2) must be reachable.
    The old formula used l_lo // r_hi = -5 // 3 = -2 and l_hi // r_lo = -3 // 2 = -2,
    producing bounds (-2, -2) and missing -5 // 2 = -3.  The correct bounds
    require computing all four corners and taking min/max.
    Use a tuple tree so both labels are SAT-encoded.
    """
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    FloorDiv = core_attr("FloorDiv")
    tree = Tuple[Annotated[int, Name("X")], Annotated[int, Name("Y")]]
    constraint = And(
        And(_int_bounds("X", -5, -3), _int_bounds("Y", 2, 3)),
        Eq(FloorDiv(ref("X"), ref("Y")), int_const(-3))
    )
    result = generate(tree, constraint, {})
    expected = {(x, y) for x in range(-5, -2) for y in range(2, 4) if x // y == -3}
    assert result == expected, f"Expected {expected}, got {result}"


def test_floordiv_bounds_negative_both():
    """FloorDiv with all-negative dividend range and constant divisor bound check."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    FloorDiv = core_attr("FloorDiv")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", -5, -1), Eq(FloorDiv(ref("X"), int_const(2)), int_const(-3)))
    result = generate(tree, constraint, {})
    expected = {v for v in range(-5, 0) if v // 2 == -3}
    assert result == expected, f"Expected {expected}, got {result}"


# --------------------------------------------------------------------------
# Zero-divisor under Or short-circuit: must NOT make model globally unsat
# --------------------------------------------------------------------------


def test_floordiv_by_zero_under_or_does_not_block_valid_solutions():
    """Or(ref("B"), Eq(FloorDiv(X, 0), 1)) with B=True must yield solutions.

    When FloorDiv(X, 0) is under an Or that can be satisfied via the other
    branch (B=True), the zero-divisor must NOT make the entire model unsat.
    """
    generate = core_attr("generate")
    Name = core_attr("Name")
    Or = core_attr("Or")
    Eq = core_attr("Eq")
    FloorDiv = core_attr("FloorDiv")
    tree = Tuple[Annotated[bool, Name("B")], Annotated[int, Name("X")]]
    bounds = _int_bounds("X", 0, 2)
    constraint = And(bounds, Or(ref("B"), Eq(FloorDiv(ref("X"), int_const(0)), int_const(1))))
    result = generate(tree, constraint, {})
    # B=True satisfies the Or regardless of X; B=False requires FloorDiv(X,0)==1 (impossible)
    expected = {(True, x) for x in range(0, 3)}
    assert result == expected, f"Expected {expected}, got {result}"


def test_mod_by_zero_under_or_does_not_block_valid_solutions():
    """Or(ref("B"), Eq(Mod(X, 0), 1)) with B=True must yield solutions."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Or = core_attr("Or")
    Eq = core_attr("Eq")
    Mod = core_attr("Mod")
    tree = Tuple[Annotated[bool, Name("B")], Annotated[int, Name("X")]]
    bounds = _int_bounds("X", 0, 2)
    constraint = And(bounds, Or(ref("B"), Eq(Mod(ref("X"), int_const(0)), int_const(1))))
    result = generate(tree, constraint, {})
    expected = {(True, x) for x in range(0, 3)}
    assert result == expected, f"Expected {expected}, got {result}"


def test_floordiv_variable_zero_divisor_under_or_short_circuit():
    """Or(ref("B"), Eq(FloorDiv(1, Y), 0)) with Y in {0,1}: B=True must include Y=0.

    The variable-divisor encoding must NOT add an unconditional Y!=0 constraint.
    When B=True the Or is satisfied regardless of Y, so (True, 0) must be a solution.
    """
    generate = core_attr("generate")
    Name = core_attr("Name")
    Or = core_attr("Or")
    Eq = core_attr("Eq")
    FloorDiv = core_attr("FloorDiv")
    tree = Tuple[Annotated[bool, Name("B")], Annotated[int, Name("Y")]]
    bounds = _int_bounds("Y", 0, 1)
    constraint = And(bounds, Or(ref("B"), Eq(FloorDiv(int_const(1), ref("Y")), int_const(0))))
    result = generate(tree, constraint, {})
    # B=True satisfies the Or regardless of Y; B=False requires FloorDiv(1,Y)==0
    # which is impossible for Y in {0,1} (Y=0 undefined, Y=1 gives 1!=0).
    expected = {(True, y) for y in range(0, 2)}
    assert result == expected, f"Expected {expected}, got {result}"


def test_mod_variable_zero_divisor_under_or_short_circuit():
    """Or(ref("B"), Eq(Mod(1, Y), 0)) with Y in {0,1}: B=True must include Y=0."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Or = core_attr("Or")
    Eq = core_attr("Eq")
    Mod = core_attr("Mod")
    tree = Tuple[Annotated[bool, Name("B")], Annotated[int, Name("Y")]]
    bounds = _int_bounds("Y", 0, 1)
    constraint = And(bounds, Or(ref("B"), Eq(Mod(int_const(1), ref("Y")), int_const(0))))
    result = generate(tree, constraint, {})
    # Y=0: Mod(1, 0) is undefined → Eq=False → Or(B, False)=B → only B=True
    # Y=1: Mod(1, 1)=0 → Eq(0,0)=True → Or(B, True)=True → both B=True and B=False
    expected: set[object] = {(True, 0), (True, 1), (False, 1)}
    assert result == expected, f"Expected {expected}, got {result}"


def test_ne_type_mismatch_with_undefined_operand_under_or():
    """Ne(FloorDiv(1, Y), bool_const) must be False when Y=0 (undefined), not True.

    The bool-vs-int type mismatch makes Ne always True when both operands are
    defined, but the result must be False when the FloorDiv operand is undefined
    (Y=0), so that the short-circuit semantics of Or are preserved.
    """
    generate = core_attr("generate")
    Name = core_attr("Name")
    Or = core_attr("Or")
    Ne = core_attr("Ne")
    FloorDiv = core_attr("FloorDiv")
    tree = Tuple[Annotated[bool, Name("B")], Annotated[int, Name("Y")]]
    bounds = _int_bounds("Y", 0, 1)
    # Ne(FloorDiv(1, Y), True): int vs bool → type mismatch → Ne=True when defined,
    # but must be False when Y=0 (FloorDiv undefined).
    # Or(B, Ne(...)): Y=0 → Ne=False → Or(B,False)=B → only B=True
    #                 Y=1 → FloorDiv(1,1)=1 vs True → Ne=True → Or=True → both B
    constraint = And(bounds, Or(ref("B"), Ne(FloorDiv(int_const(1), ref("Y")), bool_const(True))))
    result = generate(tree, constraint, {})
    expected: set[object] = {(True, 0), (True, 1), (False, 1)}
    assert result == expected, f"Expected {expected}, got {result}"


# --------------------------------------------------------------------------
# P1: _ZERO_DIV sentinel must propagate through arithmetic wrappers
# --------------------------------------------------------------------------


def test_zero_div_sentinel_propagates_through_add():
    """Eq(Add(FloorDiv(X, 0), 1), 1) must yield no solutions.

    FloorDiv(X, 0) is undefined (sentinel); Add must propagate the sentinel
    so that the surrounding Eq always evaluates to False, not True.
    """
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Add = core_attr("Add")
    FloorDiv = core_attr("FloorDiv")
    tree = Annotated[int, Name("X")]
    # FloorDiv(X, 0) is undefined; Add(undefined, 1) must also be undefined,
    # so Eq(undefined, 1) is always False → no solutions.
    constraint = And(_int_bounds("X", 0, 2), Eq(Add(FloorDiv(ref("X"), int_const(0)), int_const(1)), int_const(1)))
    result = generate(tree, constraint, {})
    expected: set[object] = set()
    assert result == expected, f"Expected {expected}, got {result}"


def test_zero_div_sentinel_propagates_through_neg():
    """Eq(Neg(FloorDiv(X, 0)), 0) must yield no solutions."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    Neg = core_attr("Neg")
    FloorDiv = core_attr("FloorDiv")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", 0, 2), Eq(Neg(FloorDiv(ref("X"), int_const(0))), int_const(0)))
    result = generate(tree, constraint, {})
    expected: set[object] = set()
    assert result == expected, f"Expected {expected}, got {result}"


def test_zero_div_sentinel_propagates_through_add_under_or():
    """Or(B, Eq(Add(FloorDiv(X, 0), 1), 1)) must allow only B=True solutions.

    Sentinel propagates: undefined → Or(B, False) = B → only (True, x) solutions.
    """
    generate = core_attr("generate")
    Name = core_attr("Name")
    Or = core_attr("Or")
    Eq = core_attr("Eq")
    Add = core_attr("Add")
    FloorDiv = core_attr("FloorDiv")
    tree = Tuple[Annotated[bool, Name("B")], Annotated[int, Name("X")]]
    bounds = _int_bounds("X", 0, 1)
    constraint = And(bounds, Or(ref("B"), Eq(Add(FloorDiv(ref("X"), int_const(0)), int_const(1)), int_const(1))))
    result = generate(tree, constraint, {})
    expected: set[object] = {(True, 0), (True, 1)}
    assert result == expected, f"Expected {expected}, got {result}"


# --------------------------------------------------------------------------
# P1: Encode boolean expressions (Eq/Ne/And/Or) as operands in _encode_arith
# --------------------------------------------------------------------------


def test_eq_of_eq_and_bool_const():
    """Eq(Eq(ref("X"), int_const(1)), bool_const(True)) must work without TypeError.

    _encode_arith must handle boolean expression nodes (Eq, Ne, And, Or) as
    operands by reifying them into a BoolVar, rather than raising TypeError.
    Semantics: Eq(X, 1) is True iff X==1, so
      Eq(Eq(X, 1), True) is satisfied iff X==1.
    """
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    tree = Annotated[int, Name("X")]
    constraint = And(_int_bounds("X", 0, 2), Eq(Eq(ref("X"), int_const(1)), bool_const(True)))
    result = generate(tree, constraint, {})
    expected: set[object] = {1}
    assert result == expected, f"Expected {expected}, got {result}"


def test_eq_of_and_and_bool_const():
    """Eq(And(Eq(X,1), Eq(Y,2)), bool_const(True)) must work without TypeError."""
    generate = core_attr("generate")
    Name = core_attr("Name")
    Eq = core_attr("Eq")
    And = core_attr("And")
    tree = Tuple[Annotated[int, Name("X")], Annotated[int, Name("Y")]]
    constraint = And(
        And(_int_bounds("X", 0, 2), _int_bounds("Y", 0, 2)),
        Eq(And(Eq(ref("X"), int_const(1)), Eq(ref("Y"), int_const(2))), bool_const(True))
    )
    result = generate(tree, constraint, {})
    expected: set[object] = {(1, 2)}
    assert result == expected, f"Expected {expected}, got {result}"


# --------------------------------------------------------------------------
# P1: Undefined-division auxiliaries must not cause duplicate CP-SAT solutions
# --------------------------------------------------------------------------


def test_floordiv_undefined_divisor_no_duplicate_sat_assignments():
    """sat_search must not return duplicate assignments when div_defined=False.

    Or(B, Eq(FloorDiv(1, Y), 0)) with Y in {0,1}: when Y=0 and B=True the
    division is undefined (div_defined=False).  Auxiliary q/r vars must be
    pinned to a single state so CP-SAT emits exactly one solution per unique
    (B, Y) label assignment, not one per (q, r) combination.
    """
    node = TupleNode((NamedNode("B", BoolNode()), NamedNode("Y", IntRangeNode(0, 1))))
    constraint = Or(Reference("B", ()), Eq(FloorDiv(IntegerConstant(1), Reference("Y", ())), IntegerConstant(0)))
    assignments = _sat_search(node, constraint)
    seen: set[frozenset[tuple[str, object]]] = set()
    for asgn in assignments:
        key: frozenset[tuple[str, object]] = frozenset(asgn.items())
        assert key not in seen, f"Duplicate assignment in sat_search result: {asgn}\nAll: {assignments}"
        seen.add(key)


def test_mod_undefined_divisor_no_duplicate_sat_assignments():
    """sat_search must not return duplicate assignments when div_defined=False (Mod).

    Same as the FloorDiv test but using Mod.
    """
    node = TupleNode((NamedNode("B", BoolNode()), NamedNode("Y", IntRangeNode(0, 1))))
    constraint = Or(Reference("B", ()), Eq(Mod(IntegerConstant(1), Reference("Y", ())), IntegerConstant(0)))
    assignments = _sat_search(node, constraint)
    seen: set[frozenset[tuple[str, object]]] = set()
    for asgn in assignments:
        key: frozenset[tuple[str, object]] = frozenset(asgn.items())
        assert key not in seen, f"Duplicate assignment in sat_search result: {asgn}\nAll: {assignments}"
        seen.add(key)


# --------------------------------------------------------------------------
# P1: Reference path must be followed when reifying enum boolean references
# --------------------------------------------------------------------------


def test_reference_path_into_enum_tuple_in_reify_constraint():
    """Or(ref("B"), ref("T", (0,))) must follow path when T is an enum label.

    T is a tuple-valued enum label always assigned (True, False).  T[0] = True,
    so Or(B, T[0]) is trivially satisfied for both B=True and B=False.  Before
    the fix, _reify_constraint evaluated T without following path (0,), so it
    treated the tuple as a non-True value and forced the branch to False,
    incorrectly dropping B=False.
    """
    node = TupleNode(
        (
            NamedNode("B", BoolNode()),
            NamedNode("T", TupleNode((LiteralNode(True), LiteralNode(False)))),
        )
    )
    # T is always (True, False); T[0]=True, so Or(B, True) must admit B=False too.
    constraint = Or(Reference("B", ()), Reference("T", (0,)))
    assignments = _sat_search(node, constraint)
    pairs = {(a["B"], a["T"]) for a in assignments}
    expected = {(True, (True, False)), (False, (True, False))}
    assert pairs == expected, f"Expected {expected}, got {pairs}"


def test_reference_path_into_enum_tuple_as_hard_constraint():
    """ref("T", (1,)) as hard constraint must be unsatisfiable when T[1] is always False.

    T is always (True, False) so T[1] = False.  Using it as a hard constraint
    must make the model unsatisfiable.  Without the path fix, _add_constraint
    sees T = (True, False) which is not False, so it treats it as True (no
    constraint added) and admits solutions.
    """
    node = TupleNode(
        (
            NamedNode("B", BoolNode()),
            NamedNode("T", TupleNode((LiteralNode(True), LiteralNode(False)))),
        )
    )
    # T[1] = False always → hard constraint is always False → no solutions.
    constraint = Reference("T", (1,))
    assignments = _sat_search(node, constraint)
    assert assignments == [], f"Expected no solutions, got {assignments}"


# --------------------------------------------------------------------------
# P1: needs_all_solutions / sequential minimization correctness
# --------------------------------------------------------------------------


def test_sat_search_enum_label_uniform_random_forces_full_enumeration():
    """uniform_random on an enum label must trigger full SAT enumeration.

    When an enum label uses "uniform_random", the multiplicity of SAT solutions
    supporting each enum value must be preserved for correct weighting.
    Sequential minimization collapses each enum branch to a single SAT solution,
    losing multiplicity information.  Full enumeration must be triggered.

    Tree: X (bool SAT) × E ("a"|"b" enum).
    Constraint: True.
    Full enumeration → 2 SAT solutions (X=False, X=True) × 2 enum values = 4 total.
    Sequential minimization → 1 SAT solution (X=False) × 2 enum values = 2 total.
    """
    node = TupleNode(
        (
            NamedNode("X", BoolNode()),
            NamedNode("E", UnionNode((LiteralNode("a"), LiteralNode("b")))),
        )
    )
    constraint = BooleanConstant(True)

    # uniform_random on the enum label alone → full SAT enumeration per branch
    full_results = _sat_search(node, constraint, {"X": "arbitrary", "E": "uniform_random"})
    # arbitrary on all labels → sequential minimization per branch
    arb_results = _sat_search(node, constraint, {"X": "arbitrary", "E": "arbitrary"})

    # Full enumeration: 2 enum values × 2 bool values = 4
    assert len(full_results) == 4, f"Expected 4 solutions with uniform_random, got {len(full_results)}: {full_results}"
    # Sequential minimization: 2 enum values × 1 bool value (canonical-min = False) = 2
    assert len(arb_results) == 2, f"Expected 2 solutions with arbitrary, got {len(arb_results)}: {arb_results}"
    # The canonical minimum for X is False, so both arbitrary results have X=False
    assert all(r["X"] is False for r in arb_results), f"Expected X=False in all arbitrary results, got {arb_results}"


def test_sat_search_arbitrary_matches_full_enumeration_plus_apply_methods():
    """all-"arbitrary" path must produce the same result as full enumeration + apply_methods.

    The sequential-minimization path is an optimisation that must be semantically
    equivalent to enumerating all solutions and then applying apply_methods with
    all-"arbitrary" methods.
    """
    node = TupleNode(
        (
            NamedNode("X", BoolNode()),
            NamedNode("Y", IntRangeNode(0, 3)),
        )
    )
    # Constraint: X == (Y > 1), i.e. X iff Y > 1
    constraint = Eq(Reference("X", ()), Gt(Reference("Y", ()), IntegerConstant(1)))

    label_order = list(labels_in_order(node))

    # Full enumeration (no methods argument → defaults to "all" for all labels)
    all_solutions = _sat_search(node, constraint)
    # Apply "arbitrary" to the full solution set
    expected = apply_methods(all_solutions, {"X": "arbitrary", "Y": "arbitrary"}, label_order)

    # Sequential minimization path (all-"arbitrary")
    arb_solutions = _sat_search(node, constraint, {"X": "arbitrary", "Y": "arbitrary"})

    assert arb_solutions == expected, (
        f"sequential minimization produced {arb_solutions}, but full-enum + apply_methods produced {expected}"
    )
