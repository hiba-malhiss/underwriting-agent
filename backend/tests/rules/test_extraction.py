"""Checks on the LLM's suggestions: what's skipped, how quotes and pages are set, and which item
each problem belongs to. The LLM is replaced by a fixed answer (the whole flow is in
test_requirements.py)."""

from app.infrastructure.document_reader import DocumentText, PageSpan
from app.rules.domain.models import Parameter, Rulebook
from app.rules.generation.extraction import check_suggestions
from tests.rules.sample import sample_rulebook

GUIDE = "guidelines.pdf"
PAGE_1 = "Applicants over 65 years of age are not eligible.\nA BMI above 40 requires a\n"
PAGE_2 = "medical report.\nHeart conditions are at the underwriter's discretion."
TEXT = DocumentText(
    PAGE_1 + PAGE_2,
    [PageSpan(1, 0, len(PAGE_1)), PageSpan(2, len(PAGE_1), len(PAGE_1) + len(PAGE_2))],
)


def source(quote: str) -> dict:
    # What the LLM sends: its own document/page guesses, which the code replaces
    return {"document": "whatever", "page": 9, "quote": quote}


def suggestion(parameters: list[dict], rules: list[dict]) -> Rulebook:
    return Rulebook.model_validate({"parameters": parameters, "rules": rules})


BMI = {
    "name": "bmi",
    "kind": "medical",
    "value_type": "number",
    "description": "Body mass index",
}
BMI_RULE = {
    "name": "high_bmi_report",
    "description": "BMI above 40 needs a medical report",
    "rule_type": "automatic",
    "conditions": {
        "match": "all",
        "items": [{"parameter": "bmi", "operator": "greater_than", "value": 40}],
    },
    "outcome": "require_document",
    "source": source("A BMI above 40 requires a medical report."),
}


def check(suggested: Rulebook, current: Rulebook | None = None):
    return check_suggestions(suggested, current, TEXT, GUIDE, based_on_version=None)


# The document and page come from where the quote really is, not from the LLM
def test_sources_are_set_from_the_document_even_across_pages():
    proposal = check(suggestion([BMI], [BMI_RULE]))
    rule = proposal.rules[0]
    assert rule.problems == []
    assert (rule.rule.source.document, rule.rule.source.page, rule.rule.source.last_page) == (
        GUIDE,
        1,
        2,  # the sentence starts on page 1 and ends on page 2
    )


def test_a_quote_not_in_the_document_is_flagged():
    made_up = {**BMI_RULE, "source": source("A BMI above 45 is not eligible.")}
    rule = check(suggestion([BMI], [made_up])).rules[0]
    assert rule.problems == ["quote not found in the document (made up or paraphrased?)"]
    assert rule.rule.source.page is None


# Additions only: a parameter with an existing name and the same type IS the existing one
def test_an_existing_parameter_is_skipped_and_can_be_used():
    current = sample_rulebook()  # already has bmi (number)
    proposal = check(suggestion([BMI], [BMI_RULE]), current)
    assert proposal.skipped == ["parameter bmi (already in the rulebook)"]
    assert proposal.parameters == []
    assert proposal.rules[0].problems == []  # high_bmi_report uses the existing bmi


def max_age_rule(name: str, conditions: dict) -> dict:
    return {
        "name": name,
        "description": "Over 65",
        "rule_type": "automatic",
        "conditions": conditions,
        "outcome": "decline",
        "source": source("Applicants over 65 years of age are not eligible."),
    }


# Duplicates are found by what a rule DOES, not by its name (the LLM renames things each run)
def test_the_same_rule_under_another_name_is_skipped():
    renamed = max_age_rule(
        "too_old",
        {
            "match": "all",
            "items": [{"parameter": "age", "operator": "greater_than", "value": 65.0}],
        },
    )
    proposal = check(suggestion([], [renamed]), sample_rulebook())
    assert proposal.skipped == ["rule too_old (same as current rule max_age)"]
    assert proposal.rules == []


# Order inside a group, and a group of one, don't make a rule different
def test_condition_order_and_single_item_groups_do_not_matter():
    a = {"parameter": "conditions", "operator": "contains", "value": "diabetes_type_2"}
    b = {
        "match": "any",
        "items": [
            {"parameter": "smoker", "operator": "equals", "value": True},
            {
                "match": "all",
                "items": [{"parameter": "bmi", "operator": "greater_than", "value": 30}],
            },
        ],
    }
    reordered = {
        "name": "diabetes_again",
        "description": "Same as diabetes_review",
        "rule_type": "automatic",
        "conditions": {"match": "all", "items": [b, a]},
        "outcome": "refer",
        "source": source("A BMI above 40 requires a medical report."),
    }
    proposal = check(suggestion([], [reordered]), sample_rulebook())
    assert proposal.skipped == ["rule diabetes_again (same as current rule diabetes_review)"]


# A rule the LLM suggests twice is kept once
def test_a_rule_suggested_twice_is_kept_once():
    conditions = {
        "match": "all",
        "items": [{"parameter": "age", "operator": "greater_than", "value": 70}],
    }
    rules = [max_age_rule("over_70", conditions), max_age_rule("older_than_70", conditions)]
    proposal = check(suggestion([], rules), sample_rulebook())
    assert [r.rule.name for r in proposal.rules] == ["over_70"]
    assert proposal.skipped == ["rule older_than_70 (same as suggested rule over_70)"]


# Same name, different meaning: kept and flagged, not silently dropped
def test_a_reused_name_with_a_different_meaning_is_flagged_not_dropped():
    different = max_age_rule(
        "max_age",
        {"match": "all", "items": [{"parameter": "age", "operator": "greater_than", "value": 70}]},
    )
    proposal = check(suggestion([], [different]), sample_rulebook())
    assert proposal.skipped == []
    assert proposal.rules[0].problems == [
        "the name 'max_age' is already used by a different rule; rename it"
    ]

    # A rulebook parameter, redefined with another type
    region = {"name": "region", "kind": "application", "description": "Region"}
    current = sample_rulebook().model_copy(
        update={
            "parameters": sample_rulebook().parameters
            + [Parameter(**region, value_type="enum", allowed_values=["north", "south"])]
        }
    )
    parameter = check(suggestion([{**region, "value_type": "text"}], []), current).parameters[0]
    assert parameter.problems[0].startswith("the name 'region' is already used by a different")


# A new parameter that no rule uses is probably made up or left over
def test_a_new_parameter_no_rule_uses_is_flagged():
    unused = {"name": "eye_colour", "kind": "medical", "value_type": "text", "description": "Eye"}
    proposal = check(suggestion([BMI, unused], [BMI_RULE]))
    problems = {p.parameter.name: p.problems for p in proposal.parameters}
    assert problems == {"bmi": [], "eye_colour": ["not used by any rule"]}


# A list in the rulebook can gain values (e.g. a new plan name): kept, and flagged for review
def test_new_values_for_an_existing_list_are_kept_and_flagged():
    current = sample_rulebook()  # conditions: diabetes_type_2, heart_disease, asthma
    conditions = {
        "name": "conditions",
        "kind": "medical",
        "value_type": "list",
        "description": "Known conditions",
        "allowed_values": ["asthma", "cancer"],
    }
    parameter = check(suggestion([conditions], []), current).parameters[0]
    assert parameter.parameter.allowed_values == [
        "diabetes_type_2",
        "heart_disease",
        "asthma",
        "cancer",
    ]
    assert parameter.problems == ["new allowed values: cancer"]


# Rulebook problems are attached to the suggested item they're about
def test_rulebook_problems_are_attached_to_their_item():
    wrong = {
        **BMI_RULE,
        "conditions": {
            "match": "all",
            "items": [{"parameter": "weight", "operator": "greater_than", "value": 1}],
        },
    }
    rule = check(suggestion([BMI], [wrong])).rules[0]
    assert rule.problems == ["unknown parameter 'weight'"]


# Judgment rules are compared by their conditions too: one table (one quote) can give several
def test_judgment_rules_with_the_same_quote_but_other_conditions_are_both_kept():
    def heart_judgment(name: str, value: int) -> dict:
        rule = max_age_rule(
            name,
            {
                "match": "all",
                "items": [{"parameter": "age", "operator": "greater_than", "value": value}],
            },
        )
        return {**rule, "rule_type": "judgment", "outcome": "refer"}

    rules = [heart_judgment("first", 50), heart_judgment("second", 60)]
    proposal = check(suggestion([], rules), sample_rulebook())
    assert [r.rule.name for r in proposal.rules] == ["first", "second"]
    assert proposal.skipped == []
