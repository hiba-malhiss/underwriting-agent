"""Reading guidelines in 2 steps: requirements (with checked quotes), then rules for them, with a
coverage check. The LLM is replaced by fixed answers."""

import asyncio
from datetime import UTC, datetime

from app.rules.models import Rulebook
from app.rules.prompts import build_requirements_prompt, build_rules_prompt
from app.rules.repository import RulebookVersion
from app.rules.requirements import (
    DraftRulebook,
    RequirementList,
    check_requirements,
    missed_requirements,
    rules_from_drafts,
)
from app.rules.service import RulesService
from tests.rules.sample import sample_rulebook
from tests.rules.test_extraction import BMI, GUIDE, TEXT

OVER_65 = "Applicants over 65 years of age are not eligible."
BMI_40 = "A BMI above 40 requires a medical report."  # runs from page 1 onto page 2
HEART = "Heart conditions are at the underwriter's discretion."


def requirements(*items: tuple[str, str]) -> RequirementList:
    """(quote, action) pairs → the step 1 answer."""
    return RequirementList.model_validate(
        {
            "requirements": [
                {"quote": quote, "summary": f"Summary of: {quote}", "action": action}
                for quote, action in items
            ]
        }
    )


def draft(*rules: tuple[str, int], parameters=(BMI,)) -> DraftRulebook:
    """(name, requirement number) pairs → the step 2 answer. Each rule tests BMI greater than
    39 + its requirement's number, so rules for different requirements aren't duplicates."""
    return DraftRulebook.model_validate(
        {
            "parameters": list(parameters),
            "rules": [
                {
                    "requirement": number,
                    "name": name,
                    "description": "BMI above 40 needs a medical report",
                    "rule_type": "automatic",
                    "conditions": {
                        "match": "all",
                        "items": [
                            {"parameter": "bmi", "operator": "greater_than", "value": 39 + number}
                        ],
                    },
                    "outcome": "require_document",
                }
                for name, number in rules
            ],
        }
    )


# ---- Step 1 ----


def test_requirements_are_numbered_and_their_quotes_checked():
    found, problems = check_requirements(
        requirements((BMI_40, "add_rule"), ("Made up sentence.", "add_rule")), TEXT, GUIDE
    )
    assert [r.number for r in found] == [1, 2]
    assert (found[0].source.page, found[0].source.last_page, found[0].problems) == (1, 2, [])
    assert found[1].problems == ["quote not found in the document (made up or paraphrased?)"]
    assert problems == ["requirement 2: quote not found in the document (made up or paraphrased?)"]


# ---- Step 2 ----


def test_a_rule_gets_its_requirements_quote_and_page():
    found, _ = check_requirements(requirements((BMI_40, "add_rule")), TEXT, GUIDE)
    rulebook, problems = rules_from_drafts(draft(("high_bmi_report", 1)), found)
    assert problems == []
    assert rulebook.rules[0].source.quote == BMI_40
    assert (rulebook.rules[0].source.page, rulebook.rules[0].source.last_page) == (1, 2)


def test_a_rule_pointing_to_no_requirement_is_left_out_and_reported():
    found, _ = check_requirements(requirements((BMI_40, "add_rule")), TEXT, GUIDE)
    rulebook, problems = rules_from_drafts(draft(("high_bmi_report", 7)), found)
    assert rulebook.rules == []
    assert problems == ["rule high_bmi_report: there is no requirement 7"]


def test_coverage_finds_requirements_with_no_rule():
    found, _ = check_requirements(
        requirements((BMI_40, "add_rule"), (OVER_65, "add_rule"), (HEART, "no_rule")), TEXT, GUIDE
    )
    missed = missed_requirements(draft(("high_bmi_report", 1)), found)
    assert [r.number for r in missed] == [2]  # 3 needs no rule


def test_the_prompts_have_the_snapshot_the_text_and_the_numbered_requirements():
    first = build_requirements_prompt(GUIDE, TEXT, sample_rulebook())
    assert "File name: guidelines.pdf" in first
    assert "- max_age: IF age greater_than 65 THEN decline" in first
    assert "[page 2]\nmedical report." in first

    found, _ = check_requirements(requirements((BMI_40, "add_rule")), TEXT, GUIDE)
    second = build_rules_prompt(found, sample_rulebook())
    assert f'1. (page 1) Summary of: {BMI_40}\n   Text: "{BMI_40}"' in second
    assert "- max_age: IF" in second


# ---- The whole flow ----


class FakeStore:
    async def download(self, name):
        return b"%PDF"


class FakeReader:
    async def read(self, data):
        return TEXT


class FakeRepository:
    def __init__(self, current: Rulebook | None):
        self.current = current

    async def get_current(self):
        return RulebookVersion(3, datetime.now(UTC), None, self.current) if self.current else None


class StepModel:
    """Answers each step from its own list, in order (the last one again if asked more)."""

    def __init__(self, step_1: list, step_2: list):
        self.answers = {RequirementList: step_1, DraftRulebook: step_2}
        self.calls = {RequirementList: [], DraftRulebook: []}

    async def structured(self, system, messages, output):
        self.calls[output].append(list(messages))
        answers = self.answers[output]
        return answers[min(len(self.calls[output]), len(answers)) - 1]


def propose(model: StepModel, current: Rulebook | None = None):
    service = RulesService(FakeStore(), FakeReader(), model, FakeRepository(current))
    return asyncio.run(service.propose_from_guideline(GUIDE))


def test_both_steps_give_a_proposal():
    model = StepModel(
        [requirements((BMI_40, "add_rule"), (HEART, "no_rule"))],
        [draft(("high_bmi_report", 1))],
    )
    proposal = propose(model, sample_rulebook())

    assert proposal.based_on_version == 3
    assert [r.rule.name for r in proposal.rules] == ["high_bmi_report"]
    assert proposal.rules[0].problems == []
    assert (proposal.missed, proposal.repair_rounds) == ([], 0)
    # Step 2 only got the requirement that needs a rule
    assert "1. (page 1)" in model.calls[DraftRulebook][0][0].content
    assert HEART not in model.calls[DraftRulebook][0][0].content


def test_a_missed_requirement_goes_back_to_the_model():
    model = StepModel(
        [requirements((BMI_40, "add_rule"), (OVER_65, "add_rule"))],
        [draft(("high_bmi_report", 1)), draft(("high_bmi_report", 1), ("too_old", 2))],
    )
    proposal = propose(model)

    repair = model.calls[DraftRulebook][1][-1].content
    assert f"- requirement 2 (page 1): Summary of: {OVER_65}: no rule written for it" in repair
    assert [r.rule.name for r in proposal.rules] == ["high_bmi_report", "too_old"]
    assert (proposal.missed, proposal.repair_rounds) == ([], 1)


def test_a_requirement_still_missed_after_the_repairs_is_shown_to_the_reviewer():
    model = StepModel(
        [requirements((BMI_40, "add_rule"), (OVER_65, "add_rule"))],
        [draft(("high_bmi_report", 1))],
    )
    proposal = propose(model)
    assert proposal.missed == [f"requirement 2 (page 1): Summary of: {OVER_65}"]


def test_no_new_requirements_means_no_second_call():
    model = StepModel([requirements((OVER_65, "already_covered"))], [])
    proposal = propose(model, sample_rulebook())
    assert model.calls[DraftRulebook] == []
    assert proposal.rules == []
