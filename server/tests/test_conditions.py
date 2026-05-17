import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from server.monitor_conditions import (
    ConditionExpression,
    ConditionExpressionGroup,
    LOGICAL,
    evaluate_expression_group,
)


def test_simple_expression():
    group = ConditionExpressionGroup(
        children=[ConditionExpression("foo", "equals", "bar")]
    )
    assert evaluate_expression_group(group, {"foo": "bar"}) is True


def test_complex_group():
    group = ConditionExpressionGroup(
        children=[
            ConditionExpression("a", "equals", "1"),
            ConditionExpression("b", "num_equals", "2", and_or=LOGICAL.OR),
        ]
    )
    assert evaluate_expression_group(group, {"a": "0", "b": 2}) is True
