"""Rulebook checks: what the LLM can get wrong, and that each problem names the rule and the fix."""

import pytest
from pydantic import ValidationError

from app.rules.models import Rulebook
from app.rules.validation import RulebookInvalidError, ensure_valid, find_problems
from tests.rules.sample import sample_rulebook


def with_rule(**changes) -> Rulebook:
    """The sample rulebook with its first rule (max_age) changed."""
    data = sample_rulebook().model_dump()
    data["rules"][0].update(changes)
    return Rulebook.model_validate(data)


def test_the_sample_rulebook_is_valid():
    assert find_problems(sample_rulebook()) == []


# Each case is a mistake an LLM could make; the message must say what to fix
@pytest.mark.parametrize(
    ("conditions", "expected"),
    [
        (
            {"all_of": [{"parameter": "weight", "operator": "greater_than", "value": 90}]},
            "unknown parameter 'weight'",
        ),
        (
            {"all_of": [{"parameter": "smoker", "operator": "greater_than", "value": True}]},
            "'greater_than' can't be used on boolean",
        ),
        (
            {"all_of": [{"parameter": "age", "operator": "greater_than", "value": "65"}]},
            "needs a number",
        ),
        (
            {"all_of": [{"parameter": "age", "operator": "greater_than", "value": True}]},
            "needs a number",
        ),
        (
            {"all_of": [{"parameter": "conditions", "operator": "contains", "value": "cancer"}]},
            "cancer not in the allowed values",
        ),
        (
            {
                "all_of": [
                    {"parameter": "conditions", "operator": "contains_any", "value": "asthma"}
                ]
            },
            "needs a list of values",
        ),
        ({"all_of": [], "any_of": None}, "can't be empty"),
        ({"all_of": [], "any_of": []}, "can't be empty"),
        (
            {
                "all_of": [{"parameter": "age", "operator": "greater_than", "value": 65}],
                "any_of": [{"parameter": "age", "operator": "less_than", "value": 18}],
            },
            "exactly one of all_of or any_of",
        ),
    ],
)
def test_condition_mistakes_are_reported_on_the_rule(conditions, expected):
    problems = find_problems(with_rule(conditions=conditions))
    assert [p.where for p in problems] == ["rule max_age"]
    assert expected in problems[0].message


def test_rule_type_must_fit_its_conditions():
    assert "needs conditions" in find_problems(with_rule(conditions=None))[0].message
    assert "always goes to a human" in find_problems(with_rule(rule_type="judgment"))[0].message


def test_parameters_are_checked_too():
    data = sample_rulebook().model_dump()
    data["parameters"].append(
        {
            "name": "region",
            "value_type": "enum",
            "description": "Region",
        }
    )
    data["parameters"].append(data["parameters"][0])  # age twice
    problems = find_problems(Rulebook.model_validate(data))
    assert {(p.where, p.message) for p in problems} == {
        ("parameter region", "enum parameters need allowed_values"),
        ("parameter age", "is defined twice"),
    }


# Shape errors (bad code format, a symbol instead of an operator word, no quote) are caught
# before the checks
@pytest.mark.parametrize(
    "change",
    [
        {"name": "Max Age"},
        {"conditions": {"all_of": [{"parameter": "age", "operator": ">=", "value": 1}]}},
        {"source": {"document": "g.pdf", "quote": ""}},
    ],
)
def test_bad_shapes_are_refused_by_the_model(change):
    with pytest.raises(ValidationError):
        with_rule(**change)


def test_ensure_valid_raises_with_every_problem():
    with pytest.raises(RulebookInvalidError) as error:
        ensure_valid(
            with_rule(
                conditions={
                    "all_of": [{"parameter": "weight", "operator": "greater_than", "value": 1}]
                }
            )
        )
    assert error.value.status_code == 400
    assert "rule max_age: unknown parameter 'weight'" in str(error.value)
