"""The repair loop: ask the model, check its answer in code, and if there are problems send them
back with its own answer, to fix. Both steps (requirements, rules) use it.

Like AUI's agent builder (validate → send the errors back → fix, at most 3 attempts). A plain
loop, no LangGraph: the flow is a straight line.
"""

from collections.abc import Callable

from pydantic import BaseModel

from app.infrastructure.llm import LanguageModel, Message
from app.rules.extraction import Proposal
from app.rules.parameter_checks import NEW_ALLOWED_VALUES
from app.rules.prompts import build_repair_prompt

# Repair rounds after the first answer, so at most 3 model calls per step. Each call takes
# around 20-40 seconds, so more rounds would make the user wait too long.
MAX_REPAIRS = 2


async def ask_with_repairs[Answer: BaseModel, Checked](
    model: LanguageModel,
    system: str,
    prompt: str,
    output: type[Answer],
    check: Callable[[Answer], tuple[Checked, list[str]]],
) -> tuple[Checked, int]:
    """The checked answer with the fewest problems (a repair can make things worse), and the
    repair round it came from (0 = the first answer). `check` returns the checked answer and
    its problems, written as "rule x: problem"."""
    conversation = [Message("user", prompt)]
    best: tuple[Checked, int, int] | None = None  # checked answer, problem count, round

    for round_number in range(MAX_REPAIRS + 1):
        answer = await model.structured(system, conversation, output)
        checked, problems = check(answer)

        if best is None or len(problems) <= best[1]:
            best = (checked, len(problems), round_number)
        if not problems or round_number == MAX_REPAIRS:
            break

        # Show the model its own answer and what's wrong with it
        conversation += [
            Message("assistant", answer.model_dump_json(exclude_none=True)),
            Message("user", build_repair_prompt(problems)),
        ]

    checked, _, round_number = best
    return checked, round_number


def problems_to_fix(proposal: Proposal) -> list[str]:
    """Every problem in a proposal, except the notes meant only for the reviewer (a list of
    allowed values that grows is fine, not a mistake)."""
    problems = [
        f"parameter {suggested.parameter.name}: {problem}"
        for suggested in proposal.parameters
        for problem in suggested.problems
        if not problem.startswith(NEW_ALLOWED_VALUES)
    ]
    problems += [
        f"rule {suggested.rule.name}: {problem}"
        for suggested in proposal.rules
        for problem in suggested.problems
    ]
    return problems
