from dataclasses import dataclass
from typing import List
from .operators import ConditionOperator

@dataclass
class ConditionVariable:
    id: str
    operators: List[ConditionOperator]
