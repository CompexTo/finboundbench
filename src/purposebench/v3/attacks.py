"""Stable protocol-v3 attack registry and instrumentation-only oracle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AttackFamily = Literal[
    "contract_policy_lifecycle",
    "workload_model_route_secret",
    "capability_data_flow",
    "release",
    "privacy",
    "evidence",
]
AttackOutcome = Literal[
    "PREVENTED",
    "FAILED_CLOSED",
    "SUCCEEDED_DETECTED",
    "SILENT_COMPROMISE",
    "INCONCLUSIVE",
]


@dataclass(frozen=True)
class AttackDefinition:
    attack_id: str
    family: AttackFamily
    required_control: str
    applicable_conditions: tuple[str, ...]


CONDITION_CONTROLS: dict[str, frozenset[str]] = {
    "B2": frozenset({"projection", "workload_binding"}),
    "P0": frozenset({"projection", "purpose_binding", "workload_binding"}),
    "P1": frozenset(
        {"projection", "purpose_binding", "workload_binding", "release"}
    ),
    "P2": frozenset(
        {
            "projection",
            "purpose_binding",
            "workload_binding",
            "release",
            "capability",
        }
    ),
    "P3": frozenset(
        {
            "projection",
            "purpose_binding",
            "workload_binding",
            "release",
            "capability",
            "evidence",
        }
    ),
    "D0": frozenset({"purpose_binding", "evidence"}),
    "D1": frozenset({"purpose_binding", "privacy", "evidence"}),
    "D2": frozenset({"purpose_binding", "privacy", "evidence"}),
    "D3": frozenset({"purpose_binding", "privacy", "evidence"}),
}


def _ids(prefix: str, count: int) -> tuple[str, ...]:
    return tuple(f"{prefix}-{index:02d}" for index in range(1, count + 1))


def attack_registry() -> tuple[AttackDefinition, ...]:
    """Return the 57 preregistered attacks in stable ID order."""

    definitions: list[AttackDefinition] = []
    contract_conditions = ("B2", "P0", "P1", "P2", "P3")
    for attack_id in _ids("CP", 10):
        if attack_id in {"CP-03", "CP-04", "CP-05"}:
            control = "projection"
        else:
            control = "purpose_binding"
        definitions.append(
            AttackDefinition(
                attack_id,
                "contract_policy_lifecycle",
                control,
                contract_conditions,
            )
        )
    for attack_id in _ids("WM", 7):
        definitions.append(
            AttackDefinition(
                attack_id,
                "workload_model_route_secret",
                "workload_binding",
                contract_conditions,
            )
        )
    for attack_id in _ids("CF", 10):
        definitions.append(
            AttackDefinition(
                attack_id,
                "capability_data_flow",
                "capability",
                ("B2", "P1", "P2", "P3"),
            )
        )
    for attack_id in _ids("RL", 10):
        definitions.append(
            AttackDefinition(
                attack_id,
                "release",
                "release",
                contract_conditions,
            )
        )
    for attack_id in _ids("DP", 10):
        definitions.append(
            AttackDefinition(
                attack_id,
                "privacy",
                "privacy",
                ("D0", "D1", "D2", "D3"),
            )
        )
    for attack_id in _ids("EV", 10):
        definitions.append(
            AttackDefinition(
                attack_id,
                "evidence",
                "evidence",
                ("B2", "P3"),
            )
        )
    registry = tuple(definitions)
    if len(registry) != 57 or len({item.attack_id for item in registry}) != 57:
        raise RuntimeError("protocol-v3 attack registry is incomplete or duplicated")
    return registry


def execute_test_double_attack(
    attack: AttackDefinition,
    condition: str,
) -> AttackOutcome:
    """Exercise classification plumbing; never use this as a security result."""

    if condition not in attack.applicable_conditions:
        raise ValueError(f"attack {attack.attack_id} does not apply to {condition}")
    controls = CONDITION_CONTROLS.get(condition, frozenset())
    if attack.required_control in controls:
        return "PREVENTED"
    if "evidence" in controls:
        return "SUCCEEDED_DETECTED"
    return "SILENT_COMPROMISE"


ATTACK_REGISTRY = attack_registry()
