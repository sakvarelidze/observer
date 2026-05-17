from __future__ import annotations
from typing import Dict
from .expression import ConditionExpression, ConditionExpressionGroup, LOGICAL
from .operators import operator_map

def evaluate_expression(expr: ConditionExpression, context: Dict[str, object]) -> bool:
    if expr.variable not in context:
        raise KeyError(f"Variable {expr.variable} missing in context")
    op = operator_map.get(expr.operator)
    if not op:
        raise ValueError(f"Unknown operator {expr.operator}")
    return op.test(context[expr.variable], expr.value)

def evaluate_expression_group(group: ConditionExpressionGroup, context: Dict[str, object]) -> bool:
    if not group.children:
        raise ValueError("ConditionExpressionGroup must contain at least one child")
    result = None
    for child in group.children:
        if isinstance(child, ConditionExpression):
            child_result = evaluate_expression(child, context)
        else:
            child_result = evaluate_expression_group(child, context)
        if result is None:
            result = child_result
        elif child.and_or == LOGICAL.OR:
            result = result or child_result
        elif child.and_or == LOGICAL.AND:
            result = result and child_result
        else:
            raise ValueError("Invalid logical operator")
    if result is None:
        raise ValueError("ConditionExpressionGroup did not result in boolean")
    return result
