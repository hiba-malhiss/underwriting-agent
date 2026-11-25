"""The snapshot: the current rulebook as short lines for the LLM."""

from app.rules.snapshot import snapshot
from tests.rules.sample import sample_rulebook


def test_one_line_per_parameter_and_per_rule():
    assert snapshot(sample_rulebook()) == "\n".join(
        [
            "PARAMETERS",
            "- age (application, number, years): Age",
            "- bmi (medical, number): Body mass index",
            "- smoker (medical, boolean): Smokes tobacco",
            "- conditions (medical, list: diabetes_type_2 | heart_disease | asthma): "
            "Known conditions",
            "",
            "RULES",
            "- max_age: IF age greater_than 65 THEN decline",
            "- smoker_review: IF smoker equals true THEN refer",
            # Nested groups get brackets
            '- diabetes_review: IF conditions contains "diabetes_type_2" AND '
            "(bmi greater_than 30 OR smoker equals true) THEN refer",
            # Judgment rules have no conditions: their description says what they're about
            "- heart_review: JUDGMENT Heart conditions at the underwriter's discretion THEN refer",
        ]
    )


def test_no_rulebook_yet():
    assert snapshot(None) == "(empty: no parameters or rules yet)"
