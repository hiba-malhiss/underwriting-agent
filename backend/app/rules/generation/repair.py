"""The repair loop: ask the model, check its answer in code, and if there are problems send them
back with its own answer, to fix. Both steps (requirements, rules) use it.

Like AUI's agent builder (validate → send the errors back → fix, at most 3 attempts). A plain
loop, no LangGraph: the flow is a straight line.

A repair NEVER removes items. Deleting a requirement or a rule also removes its problems, so
"fewest problems" would reward deleting what's hard to fix. An answer with fewer items than an
earlier one is never kept, and the model is told to send them back. What it can't fix stays,
with its problem, and the underwriter decides when reviewing.
"""

from collections.abc import Callable

from pydantic import BaseModel

from app.infrastructure.llm import LanguageModel, LanguageModelError, Message
from app.rules.generation.prompts import build_repair_prompt

# Repair rounds after the first answer, so at most 3 model calls per step. Each call takes
# around 20-40 seconds, so more rounds would make the user wait too long.
MAX_REPAIRS = 2


async def ask_with_repairs[Answer: BaseModel, Checked](
    model: LanguageModel,
    system: str,
    prompt: str,
    output: type[Answer],
    check: Callable[[Answer], tuple[Checked, list[str]]],
    count: Callable[[Answer], int],
) -> tuple[Checked, int]:
    """The checked answer with the fewest problems that removed nothing (a repair can make things
    worse), and the repair round it came from (0 = the first answer). `check` returns the
    checked answer and its problems, written as "rule x: problem"; `count` how many items an
    answer has (requirements, rules)."""
    conversation = [Message("user", prompt)]
    best: tuple[Checked, int, int] | None = None  # checked answer, problem count, round
    most_items = 0

    for round_number in range(MAX_REPAIRS + 1):
        try:
            answer = await model.structured(system, conversation, output)
        except LanguageModelError as error:  # say which step and round, to find the cause
            when = "the first answer" if round_number == 0 else f"repair {round_number}"
            raise LanguageModelError(f"{error} [{output.__name__}, {when}]") from error
        checked, problems = check(answer)

        items = count(answer)
        if items < most_items:  # it deleted instead of fixing: never kept
            problems = [
                f"you removed items: an earlier answer had {most_items}, this one has {items}. "
                "Send every item back; keep the ones you can't fix as they are",
                *problems,
            ]
        else:
            most_items = items
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
