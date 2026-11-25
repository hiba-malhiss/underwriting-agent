"""The repair loop's pieces: which problems in a proposal the model should fix, and how many
times it may try.

Like AUI's agent builder (validate → send the errors back → fix, at most 3 attempts): the code
checks the answer, and only the problems go back to the model. The loop itself is in service.py.
"""

from app.rules.extraction import Proposal
from app.rules.parameter_checks import NEW_ALLOWED_VALUES

# Repair rounds after the first answer, so at most 3 model calls. Each call reads the whole
# document again (around 20-40 seconds), so more rounds would make the user wait too long.
MAX_REPAIRS = 2


def problems_to_fix(proposal: Proposal) -> list[str]:
    """Every problem, written as "rule x: problem", except the notes meant only for the reviewer
    (a list of allowed values that grows is fine, not a mistake)."""
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
