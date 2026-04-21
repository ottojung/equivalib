from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from typing import Annotated, Any, Collection, Iterator, Literal, Sequence, Tuple, Union, cast

import pytest

from equivalib.core.expression import And, Eq, Ge, Le, Lt, Ne
from equivalib.core.name import Name as CoreName


EXT_XFAIL = pytest.mark.xfail(reason="Extensions spec not implemented yet")


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
    return And(Ge(ref(label), int_const(lo)), Le(ref(label), int_const(hi)))


def as_annotated(value: object, metadata: object) -> object:
    return Annotated.__getitem__((value, metadata))


def as_tuple(*items: object) -> object:
    return Tuple.__getitem__(items)


def as_union(*options: object) -> object:
    return Union.__getitem__(options)


def generate_with_extensions(
    tree: object,
    constraint: Any | None = None,
    methods: dict[str, str] | None = None,
    extensions: object | None = None,
) -> set[object]:
    generate = core_attr("generate")
    if constraint is None:
        constraint = true_expr()
    if methods is None:
        methods = {}
    return cast(set[object], generate(tree, constraint, methods, extensions=extensions))


@dataclass(frozen=True)
class Palette:
    name: str


@dataclass(frozen=True)
class Regex:
    pattern: str


WARM = Palette("warm")
PRIMARY = Palette("primary")
COOL = Palette("cool")
DEDUP = Palette("dedup")
FINITE_REGEX = Regex("ab|cd")
FINITE_REGEX_2 = Regex("cat|dog")
INFINITE_REGEX = Regex("a*")


class MissingInitializeExtension:
    def enumerate_all(self, owner: object) -> Iterator[object]:
        return iter(())

    def uniform_random(self, owner: object, weighted_values: Sequence[tuple[object, int]] | None = None) -> object:
        return object()

    def arbitrary(self, owner: object, values: Collection[object] | None = None) -> object:
        return object()


class MissingEnumerateAllExtension:
    def initialize(self, tree: object, constraint: Any) -> Any:
        return None

    def uniform_random(self, owner: object, weighted_values: Sequence[tuple[object, int]] | None = None) -> object:
        return object()

    def arbitrary(self, owner: object, values: Collection[object] | None = None) -> object:
        return object()


class MissingUniformRandomExtension:
    def initialize(self, tree: object, constraint: Any) -> Any:
        return None

    def enumerate_all(self, owner: object) -> Iterator[object]:
        return iter(())

    def arbitrary(self, owner: object, values: Collection[object] | None = None) -> object:
        return object()


class MissingArbitraryExtension:
    def initialize(self, tree: object, constraint: Any) -> Any:
        return None

    def enumerate_all(self, owner: object) -> Iterator[object]:
        return iter(())

    def uniform_random(self, owner: object, weighted_values: Sequence[tuple[object, int]] | None = None) -> object:
        return object()


class RecordingExtension:
    def __init__(
        self,
        *,
        initialize_return: Any = None,
        default_domain: Sequence[object] = (),
        domain_resolver: Any = None,
    ) -> None:
        self.initialize_return = initialize_return
        self.default_domain = tuple(default_domain)
        self.domain_resolver = domain_resolver
        self.initialize_calls: list[tuple[object, object]] = []
        self.enumerate_calls: list[object] = []
        self.arbitrary_calls: list[tuple[object, tuple[object, ...] | None]] = []
        self.uniform_calls: list[tuple[object, tuple[tuple[object, int], ...] | None]] = []

    def initialize(self, tree: object, constraint: Any) -> Any:
        self.initialize_calls.append((tree, constraint))
        return self.initialize_return

    def _domain(self, owner: object) -> list[object]:
        if self.domain_resolver is not None:
            return list(self.domain_resolver(owner))
        return list(self.default_domain)

    def enumerate_all(self, owner: object) -> Iterator[object]:
        self.enumerate_calls.append(owner)
        return iter(self._domain(owner))

    def arbitrary(self, owner: object, values: Collection[object] | None = None) -> object:
        snapshot = None if values is None else tuple(values)
        self.arbitrary_calls.append((owner, snapshot))
        candidates = self._domain(owner) if values is None else list(values)
        if not candidates:
            raise ValueError("No admissible values.")
        return candidates[0]

    def uniform_random(
        self,
        owner: object,
        weighted_values: Sequence[tuple[object, int]] | None = None,
    ) -> object:
        snapshot = None if weighted_values is None else tuple(weighted_values)
        self.uniform_calls.append((owner, snapshot))
        if weighted_values is not None:
            if not weighted_values:
                raise ValueError("No admissible weighted values.")
            best_weight = max(weight for _, weight in weighted_values)
            best_values = [value for value, weight in weighted_values if weight == best_weight]
            return sorted(best_values, key=repr)[-1]
        candidates = self._domain(owner)
        if not candidates:
            raise ValueError("No admissible values.")
        return candidates[-1]


class OnlyTrueBoolExtension(RecordingExtension):
    def __init__(self) -> None:
        super().__init__(default_domain=(True,))


class PreferTrueBoolExtension(RecordingExtension):
    def __init__(self) -> None:
        super().__init__(default_domain=(False, True))

    def arbitrary(self, owner: object, values: Collection[object] | None = None) -> object:
        snapshot = None if values is None else tuple(values)
        self.arbitrary_calls.append((owner, snapshot))
        candidates = self._domain(owner) if values is None else list(values)
        if True in candidates:
            return True
        if not candidates:
            raise ValueError("No admissible values.")
        return candidates[0]

    def uniform_random(
        self,
        owner: object,
        weighted_values: Sequence[tuple[object, int]] | None = None,
    ) -> object:
        snapshot = None if weighted_values is None else tuple(weighted_values)
        self.uniform_calls.append((owner, snapshot))
        if weighted_values is not None:
            true_weight = sum(weight for value, weight in weighted_values if value is True)
            false_weight = sum(weight for value, weight in weighted_values if value is False)
            if true_weight == false_weight == 0:
                raise ValueError("No admissible weighted values.")
            return True if true_weight >= false_weight else False
        return True


class RegexExtension(RecordingExtension):
    def __init__(self, initialize_return: Any = None) -> None:
        super().__init__(initialize_return=initialize_return)

    def _regex_values(self, owner: object) -> list[str] | None:
        assert isinstance(owner, Regex)
        if owner.pattern == "a*":
            return None
        return owner.pattern.split("|")

    def enumerate_all(self, owner: object) -> Iterator[object]:
        self.enumerate_calls.append(owner)
        values = self._regex_values(owner)
        if values is None:
            raise ValueError("infinite regex domain")
        return iter(values)

    def arbitrary(self, owner: object, values: Collection[object] | None = None) -> object:
        snapshot = None if values is None else tuple(values)
        self.arbitrary_calls.append((owner, snapshot))
        if values is not None:
            candidates = [cast(str, value) for value in values]
            if not candidates:
                raise ValueError("No admissible regex values.")
            return sorted(candidates)[0]
        regex_values = self._regex_values(owner)
        if regex_values is None:
            return ""
        return regex_values[0]

    def uniform_random(
        self,
        owner: object,
        weighted_values: Sequence[tuple[object, int]] | None = None,
    ) -> object:
        snapshot = None if weighted_values is None else tuple(weighted_values)
        self.uniform_calls.append((owner, snapshot))
        regex_values = self._regex_values(owner)
        if regex_values is None:
            raise ValueError("infinite regex domain")
        if weighted_values is not None:
            best_weight = max(weight for _, weight in weighted_values)
            best_values = [cast(str, value) for value, weight in weighted_values if weight == best_weight]
            return sorted(best_values)[-1]
        return regex_values[-1]


def make_palette_extension(initialize_return: Any = None) -> RecordingExtension:
    domains = {
        "warm": ("red", "orange"),
        "primary": ("red", "blue"),
        "cool": ("blue", "green"),
        "dedup": ("same", "same"),
    }
    return RecordingExtension(
        initialize_return=initialize_return,
        domain_resolver=lambda owner: domains[owner.name],
    )


# ---------------------------------------------------------------------------
# Public surface and validation
# ---------------------------------------------------------------------------


@EXT_XFAIL
def test_generate_signature_mentions_extensions_keyword():
    params = inspect.signature(core_attr("generate")).parameters
    assert "extensions" in params


@EXT_XFAIL
def test_core_exports_extension_protocol():
    assert core_attr("Extension")


@EXT_XFAIL
def test_generate_accepts_extensions_none():
    assert generate_with_extensions(Literal[True], extensions=None) == {True}


@EXT_XFAIL
def test_generate_rejects_non_mapping_extensions():
    with pytest.raises(TypeError, match="extensions.*Mapping|Mapping.*extensions"):
        generate_with_extensions(Literal[True], extensions=[object()])


@EXT_XFAIL
def test_generate_rejects_instance_extension_key():
    with pytest.raises(TypeError, match="extension.*key.*type|type.*extension.*key"):
        generate_with_extensions(WARM, extensions={WARM: make_palette_extension()})


@EXT_XFAIL
def test_generate_rejects_extension_without_initialize():
    with pytest.raises(TypeError, match="initialize"):
        generate_with_extensions(WARM, extensions={Palette: MissingInitializeExtension()})


@EXT_XFAIL
def test_generate_rejects_extension_without_enumerate_all():
    with pytest.raises(TypeError, match="enumerate_all"):
        generate_with_extensions(WARM, extensions={Palette: MissingEnumerateAllExtension()})


@EXT_XFAIL
def test_generate_rejects_extension_without_uniform_random():
    with pytest.raises(TypeError, match="uniform_random"):
        generate_with_extensions(WARM, extensions={Palette: MissingUniformRandomExtension()})


@EXT_XFAIL
def test_generate_rejects_extension_without_arbitrary():
    with pytest.raises(TypeError, match="arbitrary"):
        generate_with_extensions(WARM, extensions={Palette: MissingArbitraryExtension()})


# ---------------------------------------------------------------------------
# Initialize phase
# ---------------------------------------------------------------------------


@EXT_XFAIL
def test_initialize_called_for_used_extension():
    extension = make_palette_extension()
    generate_with_extensions(WARM, extensions={Palette: extension})
    assert len(extension.initialize_calls) == 1


@EXT_XFAIL
def test_initialize_called_for_unused_registered_extension():
    extension = make_palette_extension()
    generate_with_extensions(Literal[True], extensions={Palette: extension})
    assert len(extension.initialize_calls) == 1


@EXT_XFAIL
def test_initialize_receives_original_tree_and_constraint():
    extension = make_palette_extension()
    tree = as_tuple(Annotated[int, CoreName("X")], WARM)
    constraint = _int_bounds("X", 0, 1)
    generate_with_extensions(tree, constraint, extensions={Palette: extension})
    assert extension.initialize_calls == [(tree, constraint)]


@EXT_XFAIL
def test_initialize_none_adds_no_constraint():
    extension = make_palette_extension(initialize_return=None)
    tree = Annotated[int, CoreName("X")]
    assert generate_with_extensions(tree, _int_bounds("X", 1, 2), extensions={Palette: extension}) == {1, 2}


@EXT_XFAIL
def test_initialize_returned_constraint_is_anded_with_original():
    extension = make_palette_extension(initialize_return=Le(ref("X"), int_const(1)))
    tree = Annotated[int, CoreName("X")]
    assert generate_with_extensions(tree, _int_bounds("X", 0, 2), extensions={Palette: extension}) == {0, 1}


@EXT_XFAIL
def test_multiple_initialize_constraints_are_all_anded():
    lo_extension = make_palette_extension(initialize_return=Ge(ref("X"), int_const(1)))
    hi_extension = RegexExtension(initialize_return=Le(ref("X"), int_const(1)))
    tree = Annotated[int, CoreName("X")]
    assert generate_with_extensions(tree, _int_bounds("X", 0, 2), extensions={Palette: lo_extension, Regex: hi_extension}) == {1}


@EXT_XFAIL
def test_initialize_returning_non_expression_is_rejected():
    extension = make_palette_extension(initialize_return=123)
    with pytest.raises(TypeError, match="Expression|expression"):
        generate_with_extensions(Literal[True], extensions={Palette: extension})


@EXT_XFAIL
def test_initialize_returning_non_boolean_expression_is_rejected():
    extension = make_palette_extension(initialize_return=int_const(1))
    with pytest.raises(TypeError, match="boolean"):
        generate_with_extensions(Literal[True], extensions={Palette: extension})


@EXT_XFAIL
def test_initialize_may_force_empty_result_with_contradiction():
    lo_extension = make_palette_extension(initialize_return=Ge(ref("X"), int_const(2)))
    hi_extension = RegexExtension(initialize_return=Le(ref("X"), int_const(1)))
    tree = Annotated[int, CoreName("X")]
    assert generate_with_extensions(tree, _int_bounds("X", 0, 3), extensions={Palette: lo_extension, Regex: hi_extension}) == set()


@EXT_XFAIL
def test_initialize_constraints_participate_in_bounds_inference():
    extension = make_palette_extension(initialize_return=_int_bounds("X", 1, 2))
    tree = Tuple[Annotated[int, CoreName("X")], Literal[True]]
    assert generate_with_extensions(tree, extensions={Palette: extension}) == {(1, True), (2, True)}


# ---------------------------------------------------------------------------
# Matching and lookup
# ---------------------------------------------------------------------------


@EXT_XFAIL
def test_unknown_custom_leaf_without_extension_is_rejected():
    with pytest.raises(ValueError, match="extension|unsupported"):
        generate_with_extensions(WARM)


@EXT_XFAIL
def test_extension_matches_plain_custom_leaf():
    assert generate_with_extensions(WARM, extensions={Palette: make_palette_extension()}) == {"red", "orange"}


@EXT_XFAIL
def test_extension_matches_annotated_custom_leaf():
    tree = as_annotated(WARM, CoreName("P"))
    assert generate_with_extensions(tree, extensions={Palette: make_palette_extension()}) == {"red", "orange"}


@EXT_XFAIL
def test_extension_matches_union_branch():
    tree = as_union(WARM, Literal["fallback"])
    assert generate_with_extensions(tree, extensions={Palette: make_palette_extension()}) == {"red", "orange", "fallback"}


@EXT_XFAIL
def test_extension_matches_tuple_element():
    tree = as_tuple(WARM, Literal[1])
    assert generate_with_extensions(tree, extensions={Palette: make_palette_extension()}) == {("red", 1), ("orange", 1)}


@EXT_XFAIL
def test_extension_can_override_bool():
    assert generate_with_extensions(bool, extensions={bool: OnlyTrueBoolExtension()}) == {True}


@EXT_XFAIL
def test_bool_override_preserves_boolean_constraints():
    tree = Annotated[bool, CoreName("B")]
    assert generate_with_extensions(tree, ref("B"), extensions={bool: PreferTrueBoolExtension()}) == {True}


@EXT_XFAIL
def test_unused_extension_entries_are_ignored_after_initialize():
    extension = make_palette_extension()
    assert generate_with_extensions(Literal[True], extensions={Palette: extension}) == {True}


@EXT_XFAIL
def test_extension_may_return_runtime_type_different_from_syntax_head():
    result = generate_with_extensions(WARM, extensions={Palette: make_palette_extension()})
    assert result == {"red", "orange"}
    assert all(isinstance(value, str) for value in result)


@EXT_XFAIL
def test_two_distinct_palette_leaves_use_per_occurrence_domains():
    tree = as_tuple(WARM, COOL)
    assert generate_with_extensions(tree, extensions={Palette: make_palette_extension()}) == {
        ("red", "blue"),
        ("red", "green"),
        ("orange", "blue"),
        ("orange", "green"),
    }


# ---------------------------------------------------------------------------
# Method dispatch and repeated-label semantics
# ---------------------------------------------------------------------------


@EXT_XFAIL
def test_unnamed_extension_leaf_uses_enumerate_all():
    extension = make_palette_extension()
    assert generate_with_extensions(WARM, extensions={Palette: extension}) == {"red", "orange"}
    assert extension.enumerate_calls == [WARM]
    assert not extension.arbitrary_calls
    assert not extension.uniform_calls


@EXT_XFAIL
def test_named_extension_all_uses_enumerate_all():
    extension = make_palette_extension()
    tree = as_annotated(WARM, CoreName("P"))
    assert generate_with_extensions(tree, extensions={Palette: extension}) == {"red", "orange"}
    assert extension.enumerate_calls == [WARM]


@EXT_XFAIL
def test_named_extension_arbitrary_uses_extension_hook():
    extension = make_palette_extension()
    tree = as_annotated(WARM, CoreName("P"))
    assert generate_with_extensions(tree, methods={"P": "arbitrary"}, extensions={Palette: extension}) == {"red"}
    assert extension.arbitrary_calls


@EXT_XFAIL
def test_named_extension_uniform_random_uses_extension_hook():
    extension = make_palette_extension()
    tree = as_annotated(WARM, CoreName("P"))
    assert generate_with_extensions(tree, methods={"P": "uniform_random"}, extensions={Palette: extension}) == {"orange"}
    assert extension.uniform_calls


@EXT_XFAIL
def test_mixed_tree_uses_extension_and_default_bool_together():
    tree = as_tuple(WARM, bool)
    assert generate_with_extensions(tree, extensions={Palette: make_palette_extension()}) == {
        ("red", False),
        ("red", True),
        ("orange", False),
        ("orange", True),
    }


@EXT_XFAIL
def test_repeated_named_extension_occurrences_share_one_value():
    tree = as_tuple(
        as_annotated(WARM, CoreName("P")),
        as_annotated(WARM, CoreName("P")),
    )
    assert generate_with_extensions(tree, extensions={Palette: make_palette_extension()}) == {
        ("red", "red"),
        ("orange", "orange"),
    }


@EXT_XFAIL
def test_repeated_named_extension_occurrences_intersect_domains():
    tree = as_tuple(
        as_annotated(WARM, CoreName("P")),
        as_annotated(PRIMARY, CoreName("P")),
    )
    assert generate_with_extensions(tree, extensions={Palette: make_palette_extension()}) == {("red", "red")}


@EXT_XFAIL
def test_different_named_extension_labels_remain_independent():
    tree = as_tuple(
        as_annotated(WARM, CoreName("X")),
        as_annotated(PRIMARY, CoreName("Y")),
    )
    assert generate_with_extensions(tree, extensions={Palette: make_palette_extension()}) == {
        ("red", "red"),
        ("red", "blue"),
        ("orange", "red"),
        ("orange", "blue"),
    }


@EXT_XFAIL
def test_arbitrary_extension_result_is_singleton_subset_of_all():
    tree = as_tuple(
        as_annotated(WARM, CoreName("X")),
        as_annotated(WARM, CoreName("Y")),
    )
    constraint = Ne(ref("X"), ref("Y"))
    all_results = generate_with_extensions(tree, constraint, extensions={Palette: make_palette_extension()})
    witness = generate_with_extensions(
        tree,
        constraint,
        methods={"X": "arbitrary", "Y": "arbitrary"},
        extensions={Palette: make_palette_extension()},
    )
    assert len(witness) == 1
    assert witness <= all_results


@EXT_XFAIL
def test_uniform_random_extension_result_is_singleton_subset_of_all():
    tree = as_tuple(
        as_annotated(WARM, CoreName("X")),
        as_annotated(WARM, CoreName("Y")),
    )
    constraint = Ne(ref("X"), ref("Y"))
    all_results = generate_with_extensions(tree, constraint, extensions={Palette: make_palette_extension()})
    witness = generate_with_extensions(
        tree,
        constraint,
        methods={"X": "uniform_random", "Y": "uniform_random"},
        extensions={Palette: make_palette_extension()},
    )
    assert len(witness) == 1
    assert witness <= all_results


@EXT_XFAIL
def test_arbitrary_extension_may_override_default_bool_witness_policy():
    tree = Annotated[bool, CoreName("B")]
    assert generate_with_extensions(tree, methods={"B": "arbitrary"}, extensions={bool: PreferTrueBoolExtension()}) == {True}


# ---------------------------------------------------------------------------
# Constraint interaction and atomicity
# ---------------------------------------------------------------------------


@EXT_XFAIL
def test_extension_eq_constraint_works():
    tree = as_tuple(
        as_annotated(WARM, CoreName("X")),
        as_annotated(PRIMARY, CoreName("Y")),
    )
    assert generate_with_extensions(tree, Eq(ref("X"), ref("Y")), extensions={Palette: make_palette_extension()}) == {
        ("red", "red"),
    }


@EXT_XFAIL
def test_extension_ne_constraint_works():
    tree = as_tuple(
        as_annotated(WARM, CoreName("X")),
        as_annotated(PRIMARY, CoreName("Y")),
    )
    assert generate_with_extensions(tree, Ne(ref("X"), ref("Y")), extensions={Palette: make_palette_extension()}) == {
        ("red", "blue"),
        ("orange", "red"),
        ("orange", "blue"),
    }


@EXT_XFAIL
def test_extension_ordering_constraint_is_rejected_by_default():
    tree = as_tuple(
        as_annotated(WARM, CoreName("X")),
        as_annotated(PRIMARY, CoreName("Y")),
    )
    with pytest.raises(TypeError, match="numeric|ordering"):
        generate_with_extensions(tree, Lt(ref("X"), ref("Y")), extensions={Palette: make_palette_extension()})


@EXT_XFAIL
def test_extension_arithmetic_constraint_is_rejected_by_default():
    tree = as_annotated(WARM, CoreName("X"))
    with pytest.raises(TypeError, match="numeric|Arithmetic"):
        generate_with_extensions(tree, Eq(core_attr("Add")(ref("X"), int_const(1)), int_const(1)), extensions={Palette: make_palette_extension()})


@EXT_XFAIL
def test_extension_labels_are_atomic_for_addressing():
    tree = as_annotated(WARM, CoreName("X"))
    with pytest.raises(ValueError, match="path|tuple|address"):
        generate_with_extensions(tree, Eq(ref("X", (0,)), ref("X")), extensions={Palette: make_palette_extension()})


@EXT_XFAIL
def test_extension_results_deduplicate_by_structural_equality():
    assert generate_with_extensions(DEDUP, extensions={Palette: make_palette_extension()}) == {"same"}


# ---------------------------------------------------------------------------
# Regex extension examples
# ---------------------------------------------------------------------------


@EXT_XFAIL
def test_regex_finite_exhaustive_generation():
    assert generate_with_extensions(FINITE_REGEX, extensions={Regex: RegexExtension()}) == {"ab", "cd"}


@EXT_XFAIL
def test_regex_finite_named_all_generation():
    tree = as_annotated(FINITE_REGEX, CoreName("R"))
    assert generate_with_extensions(tree, extensions={Regex: RegexExtension()}) == {"ab", "cd"}


@EXT_XFAIL
def test_regex_finite_arbitrary_generation():
    tree = as_annotated(FINITE_REGEX, CoreName("R"))
    assert generate_with_extensions(tree, methods={"R": "arbitrary"}, extensions={Regex: RegexExtension()}) == {"ab"}


@EXT_XFAIL
def test_regex_finite_uniform_random_generation():
    tree = as_annotated(FINITE_REGEX, CoreName("R"))
    assert generate_with_extensions(tree, methods={"R": "uniform_random"}, extensions={Regex: RegexExtension()}) == {"cd"}


@EXT_XFAIL
def test_regex_infinite_exhaustive_generation_raises():
    with pytest.raises(ValueError, match="infinite"):
        generate_with_extensions(INFINITE_REGEX, extensions={Regex: RegexExtension()})


@EXT_XFAIL
def test_regex_infinite_uniform_random_raises():
    tree = as_annotated(INFINITE_REGEX, CoreName("R"))
    with pytest.raises(ValueError, match="infinite"):
        generate_with_extensions(tree, methods={"R": "uniform_random"}, extensions={Regex: RegexExtension()})


@EXT_XFAIL
def test_regex_infinite_arbitrary_returns_witness():
    tree = as_annotated(INFINITE_REGEX, CoreName("R"))
    assert generate_with_extensions(tree, methods={"R": "arbitrary"}, extensions={Regex: RegexExtension()}) == {""}


@EXT_XFAIL
def test_two_distinct_regex_leaves_preserve_per_occurrence_patterns():
    tree = as_tuple(FINITE_REGEX, FINITE_REGEX_2)
    assert generate_with_extensions(tree, extensions={Regex: RegexExtension()}) == {
        ("ab", "cat"),
        ("ab", "dog"),
        ("cd", "cat"),
        ("cd", "dog"),
    }
