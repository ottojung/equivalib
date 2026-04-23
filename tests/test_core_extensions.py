from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from typing import Annotated, Any, Iterator, Optional, Type, TypeVar, cast

import pytest

from equivalib.core.expression import And, Eq, Expression, Ge, Le
from equivalib.core.name import Name as CoreName


EXT_XFAIL = pytest.mark.xfail(reason="Interface-based class extensions not implemented yet")


T = TypeVar("T")

def core_attr(name: str) -> Any:
    module = importlib.import_module("equivalib.core")
    return getattr(module, name)


def true_expr() -> Any:
    return core_attr("BooleanExpression")(True)


def int_const(value: int) -> Any:
    return core_attr("IntegerConstant")(value)


def ref(label: str, path: tuple[int, ...] = ()) -> Any:  # noqa: D401
    return core_attr("Reference")(label, path)


def _int_bounds(label: str, lo: int, hi: int) -> Any:
    return And(Ge(ref(label), int_const(lo)), Le(ref(label), int_const(hi)))


def generate_core(
    tree: object,
    constraint: Any | None = None,
    methods: dict[str, str] | None = None,
) -> set[object]:
    generate = core_attr("generate")
    if constraint is None:
        constraint = true_expr()
    if methods is None:
        methods = {}
    return cast(set[object], generate(tree, constraint, methods))


@dataclass(frozen=True)
class NoInterfaceLeaf:
    token: str = "x"


class Palette:
    @staticmethod
    def initialize(tree: Type[T], constraint: Expression) -> Optional[Expression]:
        return None

    @staticmethod
    def enumerate_all(tree: Type[T], constraint: Expression, address: Optional[str]) -> Iterator[object]:
        del tree, constraint, address
        return iter(("red", "orange"))

    @staticmethod
    def arbitrary(tree: Type[T], constraint: Expression, address: Optional[str]) -> Optional[object]:
        del tree, constraint, address
        return "red"

    @staticmethod
    def uniform_random(tree: Type[T], constraint: Expression, address: Optional[str]) -> Optional[object]:
        del tree, constraint, address
        return "orange"


class MissingInitialize:
    @staticmethod
    def enumerate_all(tree: Type[T], constraint: Expression, address: Optional[str]) -> Iterator[object]:
        del tree, constraint, address
        return iter(())

    @staticmethod
    def arbitrary(tree: Type[T], constraint: Expression, address: Optional[str]) -> Optional[object]:
        del tree, constraint, address
        return None

    @staticmethod
    def uniform_random(tree: Type[T], constraint: Expression, address: Optional[str]) -> Optional[object]:
        del tree, constraint, address
        return None


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


@EXT_XFAIL
def test_generate_signature_has_three_arguments():
    params = inspect.signature(core_attr("generate")).parameters
    assert list(params.keys()) == ["tree", "constraint", "methods"]


# ---------------------------------------------------------------------------
# Discovery and interface validation
# ---------------------------------------------------------------------------


@EXT_XFAIL
def test_non_base_class_without_interface_is_rejected():
    with pytest.raises((TypeError, ValueError), match="unsupported|interface|initialize"):
        generate_core(NoInterfaceLeaf)


@EXT_XFAIL
def test_class_missing_required_initialize_method_is_rejected():
    with pytest.raises((TypeError, ValueError), match="initialize"):
        generate_core(MissingInitialize)


@EXT_XFAIL
def test_class_with_interface_can_drive_exhaustive_generation():
    assert generate_core(Palette) == {"red", "orange"}


# ---------------------------------------------------------------------------
# Initialize semantics
# ---------------------------------------------------------------------------


class BoundedByInitialize:
    @staticmethod
    def initialize(tree: Type[T], constraint: Expression) -> Optional[Expression]:
        del tree, constraint
        return cast(Expression, _int_bounds("X", 1, 2))

    @staticmethod
    def enumerate_all(tree: Type[T], constraint: Expression, address: Optional[str]) -> Iterator[object]:
        del tree, constraint, address
        return iter(("ok",))

    @staticmethod
    def arbitrary(tree: Type[T], constraint: Expression, address: Optional[str]) -> Optional[object]:
        del tree, constraint, address
        return "ok"

    @staticmethod
    def uniform_random(tree: Type[T], constraint: Expression, address: Optional[str]) -> Optional[object]:
        del tree, constraint, address
        return "ok"


@EXT_XFAIL
def test_initialize_constraint_is_anded_into_effective_constraint():
    tree = tuple[Annotated[int, CoreName("X")], BoundedByInitialize]
    result = generate_core(tree, _int_bounds("X", 0, 3))
    assert result == {(1, "ok"), (2, "ok")}


# ---------------------------------------------------------------------------
# Method dispatch to interface hooks
# ---------------------------------------------------------------------------


@EXT_XFAIL
def test_named_custom_class_all_uses_enumerate_all():
    tree = Annotated[Palette, CoreName("P")]
    assert generate_core(tree) == {"red", "orange"}


@EXT_XFAIL
def test_named_custom_class_arbitrary_uses_arbitrary_hook():
    tree = Annotated[Palette, CoreName("P")]
    assert generate_core(tree, methods={"P": "arbitrary"}) == {"red"}


@EXT_XFAIL
def test_named_custom_class_uniform_random_uses_uniform_random_hook():
    tree = Annotated[Palette, CoreName("P")]
    assert generate_core(tree, methods={"P": "uniform_random"}) == {"orange"}


# ---------------------------------------------------------------------------
# Address semantics and atomicity
# ---------------------------------------------------------------------------


@EXT_XFAIL
def test_custom_class_address_from_name_and_tuple_path():
    tree = tuple[Annotated[Palette, CoreName("P")], Annotated[Palette, CoreName("Q")]]
    all_results = generate_core(tree)
    assert ("red", "red") in all_results


@EXT_XFAIL
def test_custom_class_leaf_remains_atomic_for_subpaths():
    tree = Annotated[Palette, CoreName("P")]
    with pytest.raises((TypeError, ValueError), match="path|atomic|address"):
        generate_core(tree, Eq(ref("P", (0,)), ref("P")))


# ---------------------------------------------------------------------------
# Built-ins remain built-ins
# ---------------------------------------------------------------------------


@EXT_XFAIL
def test_bool_behavior_still_uses_core_semantics():
    assert generate_core(bool) == {False, True}


@EXT_XFAIL
def test_int_behavior_still_uses_core_semantics():
    tree = Annotated[int, CoreName("X")]
    assert generate_core(tree, _int_bounds("X", 1, 2)) == {1, 2}

