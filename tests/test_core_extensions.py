from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, Iterator, cast

import pytest

from equivalib.core import Extension, Regex
from equivalib.core.expression import And, Eq, Expression, Ge, Le
from equivalib.core.name import Name as CoreName

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
class NotExtensionLeaf:
    token: str = "x"


@dataclass(frozen=True)
class Palette(Extension):
    token: str

    @staticmethod
    def initialize(tree: object, constraint: Expression) -> Expression | None:
        return None

    @staticmethod
    def enumerate_all(tree: object, constraint: Expression, address: str | None) -> Iterator["Palette"]:
        del tree, constraint, address
        return iter((Palette("red"), Palette("orange")))

    @staticmethod
    def arbitrary(tree: object, constraint: Expression, address: str | None) -> "Palette" | None:
        del tree, constraint, address
        return Palette("red")

    @staticmethod
    def uniform_random(tree: object, constraint: Expression, address: str | None) -> "Palette" | None:
        del tree, constraint, address
        return Palette("orange")


class InvalidInitialize(Extension):
    @staticmethod
    def enumerate_all(tree: object, constraint: Expression, address: str | None) -> Iterator["InvalidInitialize"]:
        del tree, constraint, address
        return iter(())

    @staticmethod
    def arbitrary(tree: object, constraint: Expression, address: str | None) -> "InvalidInitialize" | None:
        del tree, constraint, address
        return None

    @staticmethod
    def uniform_random(tree: object, constraint: Expression, address: str | None) -> "InvalidInitialize" | None:
        del tree, constraint, address
        return None


setattr(InvalidInitialize, "initialize", None)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_generate_signature_has_three_arguments():
    params = inspect.signature(core_attr("generate")).parameters
    assert list(params.keys()) == ["tree", "constraint", "methods"]


# ---------------------------------------------------------------------------
# Discovery and interface validation
# ---------------------------------------------------------------------------


def test_non_base_class_not_subtype_of_extension_is_rejected():
    with pytest.raises((TypeError, ValueError), match="unsupported|Extension|subtype"):
        generate_core(NotExtensionLeaf)


def test_class_missing_required_initialize_method_is_rejected():
    with pytest.raises((TypeError, ValueError), match="initialize"):
        generate_core(InvalidInitialize)


def test_extension_subclass_can_drive_exhaustive_generation():
    assert generate_core(Palette) == {Palette("red"), Palette("orange")}


# ---------------------------------------------------------------------------
# Initialize semantics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoundedByInitialize(Extension):
    @staticmethod
    def initialize(tree: object, constraint: Expression) -> Expression | None:
        del tree, constraint
        return cast(Expression, _int_bounds("X", 1, 2))

    @staticmethod
    def enumerate_all(tree: object, constraint: Expression, address: str | None) -> Iterator["BoundedByInitialize"]:
        del tree, constraint, address
        return iter((BoundedByInitialize(),))

    @staticmethod
    def arbitrary(tree: object, constraint: Expression, address: str | None) -> "BoundedByInitialize" | None:
        del tree, constraint, address
        return BoundedByInitialize()

    @staticmethod
    def uniform_random(tree: object, constraint: Expression, address: str | None) -> "BoundedByInitialize" | None:
        del tree, constraint, address
        return BoundedByInitialize()


def test_initialize_constraint_is_anded_into_effective_constraint():
    tree = tuple[Annotated[int, CoreName("X")], BoundedByInitialize]
    result = generate_core(tree, _int_bounds("X", 0, 3))
    assert result == {(1, BoundedByInitialize()), (2, BoundedByInitialize())}


# ---------------------------------------------------------------------------
# Method dispatch to Extension hooks
# ---------------------------------------------------------------------------


def test_named_custom_class_all_uses_enumerate_all():
    tree = Annotated[Palette, CoreName("P")]
    assert generate_core(tree) == {Palette("red"), Palette("orange")}


def test_named_custom_class_arbitrary_uses_arbitrary_hook():
    tree = Annotated[Palette, CoreName("P")]
    assert generate_core(tree, methods={"P": "arbitrary"}) == {Palette("red")}


def test_named_custom_class_uniform_random_uses_uniform_random_hook():
    tree = Annotated[Palette, CoreName("P")]
    assert generate_core(tree, methods={"P": "uniform_random"}) == {Palette("orange")}


# ---------------------------------------------------------------------------
# Address semantics and atomicity
# ---------------------------------------------------------------------------


def test_custom_class_address_from_name_and_tuple_path():
    tree = tuple[Annotated[Palette, CoreName("P")], Annotated[Palette, CoreName("Q")]]
    all_results = generate_core(tree)
    assert (Palette("red"), Palette("red")) in all_results


def test_custom_class_leaf_remains_atomic_for_subpaths():
    tree = Annotated[Palette, CoreName("P")]
    with pytest.raises((TypeError, ValueError), match="path|atomic|address"):
        generate_core(tree, Eq(ref("P", (0,)), ref("P")))


# ---------------------------------------------------------------------------
# Built-ins remain built-ins
# ---------------------------------------------------------------------------


def test_bool_behavior_still_uses_core_semantics():
    assert generate_core(bool) == {False, True}


def test_int_behavior_still_uses_core_semantics():
    tree = Annotated[int, CoreName("X")]
    assert generate_core(tree, _int_bounds("X", 1, 2)) == {1, 2}


class BadPalette(Palette):
    @staticmethod
    def arbitrary(tree: object, constraint: Expression, address: str | None) -> Palette | None:
        del tree, constraint, address
        return Palette("red")


def test_arbitrary_must_return_concrete_subclass_instance():
    tree = Annotated[BadPalette, CoreName("P")]
    with pytest.raises(TypeError, match="non-BadPalette"):
        generate_core(tree, methods={"P": "arbitrary"})


class RegexABorCD(Regex):
    @staticmethod
    def expression() -> str:
        return "(ab|cd)"


class RegexDigits3(Regex):
    @staticmethod
    def expression() -> str:
        return r"\d{3}"


def test_regex_extension_enumerates_concrete_language():
    assert generate_core(RegexABorCD) == {RegexABorCD("ab"), RegexABorCD("cd")}


def test_regex_extension_arbitrary_and_uniform_random_return_subclass():
    arb = generate_core(Annotated[RegexABorCD, CoreName("R")], methods={"R": "arbitrary"})
    rand = generate_core(Annotated[RegexABorCD, CoreName("R")], methods={"R": "uniform_random"})
    assert arb <= {RegexABorCD("ab"), RegexABorCD("cd")}
    assert rand <= {RegexABorCD("ab"), RegexABorCD("cd")}


def test_regex_extension_handles_repetition_and_ranges():
    values = generate_core(RegexDigits3)
    assert len(values) == 1000
    assert RegexDigits3("000") in values
    assert RegexDigits3("999") in values


@dataclass(frozen=True)
class AddressEcho(Extension):
    token: str
    seen_addresses: ClassVar[list[str | None]] = []

    @staticmethod
    def initialize(tree: object, constraint: Expression) -> Expression | None:
        del tree, constraint
        return None

    @staticmethod
    def enumerate_all(tree: object, constraint: Expression, address: str | None) -> Iterator["AddressEcho"]:
        del tree, constraint
        AddressEcho.seen_addresses.append(address)
        return iter((AddressEcho("ok"),))

    @staticmethod
    def arbitrary(tree: object, constraint: Expression, address: str | None) -> "AddressEcho" | None:
        del tree, constraint
        AddressEcho.seen_addresses.append(address)
        return AddressEcho("ok")

    @staticmethod
    def uniform_random(tree: object, constraint: Expression, address: str | None) -> "AddressEcho" | None:
        del tree, constraint
        AddressEcho.seen_addresses.append(address)
        return AddressEcho("ok")


def test_extension_address_uses_bracket_notation_from_named_tuple_path():
    AddressEcho.seen_addresses.clear()
    tree = Annotated[tuple[bool, tuple[AddressEcho]], CoreName("X")]
    result = generate_core(tree, methods={"X": "arbitrary"})
    assert result == {(False, (AddressEcho("ok"),))}
    assert AddressEcho.seen_addresses == ["X[1][0]"]


def test_extension_address_uses_bracket_notation_from_unnamed_tuple_path():
    AddressEcho.seen_addresses.clear()
    tree = tuple[bool, tuple[AddressEcho]]
    result = generate_core(tree)
    assert result == {(False, (AddressEcho("ok"),)), (True, (AddressEcho("ok"),))}
    assert AddressEcho.seen_addresses == ["[1][0]"]
