"""Reading guidelines in 2 steps, so a missed rule shows up as a problem instead of silence.

Step 1, requirements: the LLM lists every statement in the text that decides something about an
applicant, each with its exact quote, marked add_rule / already_covered / no_rule. Code checks
every quote is really in the text.

Step 2, rules: the LLM gets the add_rule requirements, numbered, and writes the parameters and
rules for them; each rule says which requirement it encodes. Code then:
- gives each rule its requirement's (already checked) quote as its source, so step 2 can't
  invent a quote;
- checks coverage: every add_rule requirement has at least one rule.

Nothing is saved here. The rules then go through the usual checks (extraction.py).
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import Field

from app.infrastructure.document_reader import DocumentText
from app.rules.extraction import locate_quote
from app.rules.models import Parameter, Rule, Rulebook, RuleLogic, Source, Strict

# add_rule: an exception (decline, review, a document, extra terms) no current rule covers yet
# already_covered: a current rule already does this · no_rule: it only says something is fine
Action = Literal["add_rule", "already_covered", "no_rule"]


# ---- Step 1: what the LLM answers, and what code makes of it ----


class Requirement(Strict):
    quote: str = Field(min_length=1)
    summary: str  # the requirement in one full sentence, readable without the text
    action: Action


class RequirementList(Strict):
    requirements: list[Requirement]


@dataclass(frozen=True)
class FoundRequirement:
    number: int  # 1, 2, 3…: how step 2 and the reviewer refer to it
    summary: str
    action: Action
    source: Source  # with the real page(s) when the quote was found
    problems: list[str] = field(default_factory=list)


def check_requirements(answer: RequirementList, text: DocumentText, document_name: str):
    """Number the requirements and check each quote is in the text."""
    found = []
    for number, requirement in enumerate(answer.requirements, start=1):
        source, problems = locate_quote(requirement.quote, text, document_name)
        found.append(
            FoundRequirement(number, requirement.summary, requirement.action, source, problems)
        )
    return found


def requirement_problems(requirements: list[FoundRequirement]) -> list[str]:
    return [f"requirement {r.number}: {problem}" for r in requirements for problem in r.problems]


# ---- Step 2: the rules for the add_rule requirements ----


class DraftRule(RuleLogic):
    requirement: int  # the number of the requirement this rule encodes


class DraftRulebook(Strict):
    parameters: list[Parameter]  # first, like AUI: the rules below may only use known ones
    rules: list[DraftRule]


def rules_from_drafts(
    draft: DraftRulebook, requirements: list[FoundRequirement]
) -> tuple[Rulebook, list[str]]:
    """The drafts as rules, each with its requirement's source. A rule pointing to a requirement
    that doesn't exist has no source to show, so it's left out and reported."""
    by_number = {r.number: r for r in requirements}
    rules, problems = [], []
    for rule in draft.rules:
        requirement = by_number.get(rule.requirement)
        if requirement is None:
            problems.append(f"rule {rule.name}: there is no requirement {rule.requirement}")
            continue
        logic = rule.model_dump(exclude={"requirement"})
        rules.append(Rule.model_validate({**logic, "source": requirement.source.model_dump()}))
    return Rulebook(parameters=draft.parameters, rules=rules), problems


def missed_requirements(
    draft: DraftRulebook, requirements: list[FoundRequirement]
) -> list[FoundRequirement]:
    """Coverage: the add_rule requirements no rule was written for."""
    covered = {rule.requirement for rule in draft.rules}
    return [r for r in requirements if r.action == "add_rule" and r.number not in covered]


def describe(requirement: FoundRequirement) -> str:
    """ "requirement 3 (page 2): Applicants aged 65 or over are not eligible." """
    page = f" (page {requirement.source.page})" if requirement.source.page else ""
    return f"requirement {requirement.number}{page}: {requirement.summary}"
