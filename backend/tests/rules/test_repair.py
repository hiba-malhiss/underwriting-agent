"""The repair loop: problems in the model's answer go back to it, at most MAX_REPAIRS times, and
the answer with the fewest problems is kept. The model is replaced by a list of fixed answers."""

import asyncio

from app.rules.extraction import Proposal, SuggestedParameter
from app.rules.models import Parameter
from app.rules.repair import MAX_REPAIRS, problems_to_fix
from app.rules.service import RulesService
from tests.rules.test_extraction import (
    BMI,
    BMI_RULE,
    GUIDE,
    FakeReader,
    FakeRepository,
    FakeStore,
    source,
    suggestion,
)

GOOD = suggestion([BMI], [BMI_RULE])
BAD_QUOTE = suggestion([BMI], [{**BMI_RULE, "source": source("BMI over 40 needs a report.")}])


class ScriptedModel:
    """Gives its answers in order (the last one again if asked more), and keeps every
    conversation it was sent."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.conversations = []

    async def structured(self, system, messages, output):
        self.conversations.append(list(messages))
        return self.answers[min(len(self.conversations), len(self.answers)) - 1]


def propose(model: ScriptedModel) -> Proposal:
    service = RulesService(FakeStore(), FakeReader(), model, FakeRepository(None))
    return asyncio.run(service.propose_from_guideline(GUIDE))


def test_a_clean_answer_needs_no_repair():
    model = ScriptedModel(GOOD)
    proposal = propose(model)
    assert len(model.conversations) == 1
    assert proposal.repair_rounds == 0


def test_problems_go_back_to_the_model_with_its_own_answer():
    model = ScriptedModel(BAD_QUOTE, GOOD)
    proposal = propose(model)

    assert len(model.conversations) == 2
    _, its_answer, repair = model.conversations[1]
    assert its_answer.role == "assistant" and "BMI over 40 needs a report." in its_answer.content
    assert repair.role == "user"
    assert "- rule high_bmi_report: quote not found" in repair.content
    assert proposal.repair_rounds == 1
    assert proposal.rules[0].problems == []


def test_it_stops_after_max_repairs_and_keeps_the_problems_for_review():
    model = ScriptedModel(BAD_QUOTE)
    proposal = propose(model)
    assert len(model.conversations) == 1 + MAX_REPAIRS
    assert proposal.rules[0].problems  # the reviewer still sees them


def test_a_worse_repair_is_not_kept():
    two_bad = suggestion(
        [BMI],
        [
            {**BMI_RULE, "source": source("made up")},
            {
                **BMI_RULE,
                "name": "very_high_bmi",
                "conditions": {
                    "match": "all",
                    "items": [{"parameter": "bmi", "operator": "greater_than", "value": 50}],
                },
                "source": source("also made up"),
            },
        ],
    )
    model = ScriptedModel(BAD_QUOTE, two_bad)
    proposal = propose(model)
    assert [r.rule.name for r in proposal.rules] == ["high_bmi_report"]
    assert proposal.repair_rounds == 0


def test_new_allowed_values_are_a_note_for_the_reviewer_not_a_problem_to_fix():
    plan = Parameter(
        name="plan",
        kind="application",
        value_type="enum",
        description="Plan",
        allowed_values=["basic", "gold"],
    )
    proposal = Proposal(
        based_on_version=1,
        document=GUIDE,
        parameters=[SuggestedParameter(plan, ["new allowed values: gold", "not used by any rule"])],
        rules=[],
        skipped=[],
    )
    assert problems_to_fix(proposal) == ["parameter plan: not used by any rule"]
