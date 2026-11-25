"""Running rules: each status, nested groups, and that missing values never pass silently."""

import pytest

from app.rules.evaluator import evaluate
from tests.rules.sample import sample_rulebook


def results(values: dict) -> dict:
    return {r.rule_name: r for r in evaluate(sample_rulebook(), values)}


def test_a_healthy_applicant_passes_every_rule():
    r = results({"age": 40, "bmi": 24.5, "smoker": False, "conditions": []})
    assert {code: x.status for code, x in r.items()} == {
        "max_age": "passed",
        "smoker_review": "passed",
        "diabetes_review": "passed",
        "heart_review": "needs_judgment",  # judgment rules always go to a human
    }
    assert r["max_age"].explanation == "age is 40 (not more than 65)"


def test_a_rule_not_passed_gives_its_outcome_and_explanation():
    r = results({"age": 70, "bmi": 24, "smoker": True, "conditions": []})
    assert (r["max_age"].status, r["max_age"].outcome) == ("not_passed", "decline")
    assert r["max_age"].explanation == "age is 70 (more than 65)"
    assert (r["smoker_review"].status, r["smoker_review"].outcome) == (
        "not_passed",
        "refer",
    )


# A missing value is missing_data, never a pass
def test_missing_value_is_missing_data_not_passed():
    r = results({"bmi": 24, "smoker": False, "conditions": []})  # no age
    assert r["max_age"].status == "missing_data"
    assert r["max_age"].missing_parameters == ["age"]
    assert r["max_age"].explanation == "Missing: age"


# Three-valued logic: a missing value only matters when it could change the answer
@pytest.mark.parametrize(
    ("values", "status"),
    [
        # diabetes AND (bmi > 30 OR smoker)
        ({"conditions": ["diabetes_type_2"], "bmi": 33, "smoker": False}, "not_passed"),
        ({"conditions": ["diabetes_type_2"], "smoker": True}, "not_passed"),  # OR already true
        ({"conditions": ["asthma"]}, "passed"),  # AND already false: bmi doesn't matter
        ({"conditions": ["diabetes_type_2"], "smoker": False}, "missing_data"),  # needs bmi
        ({"bmi": 40, "smoker": True}, "missing_data"),  # needs conditions
    ],
)
def test_nested_groups_with_missing_values(values, status):
    assert results(values)["diabetes_review"].status == status


def test_a_value_of_the_wrong_type_is_missing_data():
    r = results({"age": "seventy"})
    assert r["max_age"].status == "missing_data"
    assert r["max_age"].missing_parameters == ["age"]
