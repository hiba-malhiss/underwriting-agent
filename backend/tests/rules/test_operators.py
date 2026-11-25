"""The operators between, is_missing and is_present."""

import pytest

from app.rules.evaluator import evaluate
from app.rules.models import Rulebook
from app.rules.validation import find_problems
from tests.rules.sample import source


def rulebook(condition: dict, value_type: str = "number") -> Rulebook:
    return Rulebook.model_validate(
        {
            "parameters": [
                {
                    "name": "age",
                    "kind": "application",
                    "value_type": "number",
                    "description": "Age",
                },
                {"name": "hba1c", "kind": "medical", "value_type": value_type, "description": "x"},
            ],
            "rules": [
                {
                    "name": "check",
                    "description": "test rule",
                    "rule_type": "automatic",
                    "conditions": {"match": "all", "items": [condition]},
                    "outcome": "refer",
                    "source": source("quote"),
                }
            ],
        }
    )


def status(condition: dict, values: dict) -> str:
    return evaluate(rulebook(condition), values)[0].status


# between: inclusive on both ends
@pytest.mark.parametrize(
    ("age", "expected"), [(49, "passed"), (50, "not_passed"), (59, "not_passed")]
)
def test_between_includes_both_ends(age, expected):
    condition = {"parameter": "age", "operator": "between", "value": [50, 59]}
    assert status(condition, {"age": age}) == expected


# is_missing / is_present: a missing value is the ANSWER here, never "missing data"
def test_presence_operators_never_give_missing_data():
    missing = {"parameter": "hba1c", "operator": "is_missing"}
    present = {"parameter": "hba1c", "operator": "is_present"}
    assert status(missing, {}) == "not_passed"
    assert status(missing, {"hba1c": 6.1}) == "passed"
    assert status(present, {}) == "passed"


@pytest.mark.parametrize(
    ("condition", "problem"),
    [
        ({"parameter": "age", "operator": "between", "value": 50}, "needs [low, high]"),
        ({"parameter": "age", "operator": "between", "value": [60, 50]}, "low is bigger"),
        ({"parameter": "hba1c", "operator": "is_missing", "value": 7}, "takes no value"),
        ({"parameter": "age", "operator": "greater_than"}, "needs a value"),
    ],
)
def test_operator_value_shapes_are_checked(condition, problem):
    problems = find_problems(rulebook(condition))
    assert problem in problems[0].message
