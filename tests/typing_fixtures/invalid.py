"""Deliberately invalid input used to verify the configured ty diagnostics."""

from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    pass


bad_assignment: int = "not an integer"
missing_generic_argument: Box = Box()
possibly_missing = unresolved_name


def invalid_route_return() -> dict[str, str]:
    return ["not", "a", "mapping"]
