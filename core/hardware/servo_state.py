"""Immutable result of an explicitly requested servo transition."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServoTransition:
    initial_state: int
    final_state: int
    actions: tuple[str, ...]
