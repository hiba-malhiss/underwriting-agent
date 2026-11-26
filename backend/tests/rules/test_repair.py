"""The repair loop: problems in the model's answer go back to it with its own answer, at most
MAX_REPAIRS times, and the answer with the fewest problems is kept."""

import asyncio

from pydantic import BaseModel

from app.rules.domain.models import Parameter
from app.rules.generation.extraction import Proposal, SuggestedParameter, problems_to_fix
from app.rules.generation.repair import MAX_REPAIRS, ask_with_repairs


class Answer(BaseModel):
    words: list[str]


class ScriptedModel:
    """Gives its answers in order (the last one again if asked more), and keeps every
    conversation it was sent."""

    def __init__(self, *answers: list[str]):
        self.answers = [Answer(words=a) for a in answers]
        self.conversations = []

    async def structured(self, system, messages, output):
        self.conversations.append(list(messages))
        return self.answers[min(len(self.conversations), len(self.answers)) - 1]


def no_bad_words(answer: Answer):
    """The check: every "bad" word is a problem."""
    return answer.words, [f"word {i}: bad" for i, w in enumerate(answer.words) if w == "bad"]


def ask(model: ScriptedModel):
    return asyncio.run(ask_with_repairs(model, "system", "first prompt", Answer, no_bad_words))


def test_a_clean_answer_needs_no_repair():
    model = ScriptedModel(["good"])
    assert ask(model) == (["good"], 0)
    assert len(model.conversations) == 1


def test_problems_go_back_to_the_model_with_its_own_answer():
    model = ScriptedModel(["bad", "good"], ["good", "good"])
    assert ask(model) == (["good", "good"], 1)

    first, its_answer, repair = model.conversations[1]
    assert first.content == "first prompt"
    assert (its_answer.role, its_answer.content) == ("assistant", '{"words":["bad","good"]}')
    assert repair.role == "user" and "- word 0: bad" in repair.content


def test_it_stops_after_max_repairs_and_keeps_the_problems():
    model = ScriptedModel(["bad"])
    assert ask(model) == (["bad"], MAX_REPAIRS)
    assert len(model.conversations) == 1 + MAX_REPAIRS


def test_a_worse_repair_is_not_kept():
    model = ScriptedModel(["bad"], ["bad", "bad"])
    assert ask(model) == (["bad"], 0)


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
        document="guidelines.pdf",
        parameters=[SuggestedParameter(plan, ["new allowed values: gold", "not used by any rule"])],
        rules=[],
        skipped=[],
    )
    assert problems_to_fix(proposal) == ["parameter plan: not used by any rule"]
