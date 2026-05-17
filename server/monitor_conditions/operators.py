from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

@dataclass
class ConditionOperator:
    id: str
    caption: str
    test: Callable[[Any, str], bool]


def _eq(var: Any, value: str) -> bool:
    return var == value

def _neq(var: Any, value: str) -> bool:
    return var != value

def _contains(var: Any, value: str) -> bool:
    return value in var

def _not_contains(var: Any, value: str) -> bool:
    return value not in var

def _starts_with(var: str, value: str) -> bool:
    return str(var).startswith(value)

def _not_starts_with(var: str, value: str) -> bool:
    return not str(var).startswith(value)

def _ends_with(var: str, value: str) -> bool:
    return str(var).endswith(value)

def _not_ends_with(var: str, value: str) -> bool:
    return not str(var).endswith(value)

def _num_eq(var: Any, value: str) -> bool:
    return float(var) == float(value)

def _num_neq(var: Any, value: str) -> bool:
    return float(var) != float(value)

def _lt(var: Any, value: str) -> bool:
    return float(var) < float(value)

def _gt(var: Any, value: str) -> bool:
    return float(var) > float(value)

def _lte(var: Any, value: str) -> bool:
    return float(var) <= float(value)

def _gte(var: Any, value: str) -> bool:
    return float(var) >= float(value)

operator_map: Dict[str, ConditionOperator] = {
    "equals": ConditionOperator("equals", "equals", _eq),
    "not_equals": ConditionOperator("not_equals", "not equals", _neq),
    "contains": ConditionOperator("contains", "contains", _contains),
    "not_contains": ConditionOperator("not_contains", "not contains", _not_contains),
    "starts_with": ConditionOperator("starts_with", "starts with", _starts_with),
    "not_starts_with": ConditionOperator("not_starts_with", "not starts with", _not_starts_with),
    "ends_with": ConditionOperator("ends_with", "ends with", _ends_with),
    "not_ends_with": ConditionOperator("not_ends_with", "not ends with", _not_ends_with),
    "num_equals": ConditionOperator("num_equals", "equals", _num_eq),
    "num_not_equals": ConditionOperator("num_not_equals", "not equals", _num_neq),
    "lt": ConditionOperator("lt", "less than", _lt),
    "gt": ConditionOperator("gt", "greater than", _gt),
    "lte": ConditionOperator("lte", "less than or equal", _lte),
    "gte": ConditionOperator("gte", "greater than or equal", _gte),
}

default_string_operators: List[ConditionOperator] = [
    operator_map["equals"],
    operator_map["not_equals"],
    operator_map["contains"],
    operator_map["not_contains"],
    operator_map["starts_with"],
    operator_map["not_starts_with"],
    operator_map["ends_with"],
    operator_map["not_ends_with"],
]

default_number_operators: List[ConditionOperator] = [
    operator_map["num_equals"],
    operator_map["num_not_equals"],
    operator_map["lt"],
    operator_map["gt"],
    operator_map["lte"],
    operator_map["gte"],
]
