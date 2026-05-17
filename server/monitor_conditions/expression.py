from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Union

class LOGICAL(str, Enum):
    AND = "and"
    OR = "or"

@dataclass
class ConditionExpression:
    variable: str
    operator: str
    value: str
    and_or: LOGICAL = LOGICAL.AND

@dataclass
class ConditionExpressionGroup:
    children: List[Union["ConditionExpression", "ConditionExpressionGroup"]] = field(default_factory=list)
    and_or: LOGICAL = LOGICAL.AND
