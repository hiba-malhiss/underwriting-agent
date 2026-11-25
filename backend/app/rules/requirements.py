"""Reading guidelines in 2 steps, so a missed rule shows up as a problem instead of silence.

Step 1, requirements: the LLM lists every statement in the text that decides something about an
applicant, each with its exact quote and the OUTCOME THE TEXT STATES (accept, accept with terms,
refer, decline, a document). It only copies what the text says; CODE decides what needs a rule:
nothing for "accept", nothing when a current rule already covers it (and that rule must exist).
Code also checks every quote is really in the text.

Step 2, rules: the LLM gets the requirements that need a rule, numbered, and writes the
parameters and rules for them; each rule says which requirement it encodes. Code then:
- gives each rule its requirement's (already checked) quote as its source, so step 2 can't
  invent a quote;
- checks each rule's outcome is the one its requirement states (a "refer" rule for a line that
  says "Accept, standard terms" is a problem);
- checks coverage: every requirement that needs a rule has at least one.

Nothing is saved here. The rules then go through the usual checks (extraction.py).
"""

from dataclasses import dataclass, field, replace
from typing import Literal

from pydantic import Field

from app.infrastructure.document_reader import DocumentText
from app.rules.extraction import Proposal, check_suggestions, locate_quote, problems_to_fix
from app.rules.models import Outcome, Parameter, Rule, Rulebook, RuleLogic, Source, Strict

# What the text says happens to the applicant. accept: eligible on standard terms (needs no
# rule); accept_with_terms: eligible with a waiting period, an exclusion or a loading
StatedOutcome = Literal["accept", "accept_with_terms", "refer", "decline", "require_document"]

# The rule outcome each stated outcome needs (None: no rule). Accept with terms is referred for
# now: the rules have no outcome for terms yet
RULE_OUTCOME: dict[StatedOutcome, Outcome | None] = {
    "accept": None,
    "accept_with_terms": "refer",
    "refer": "refer",
    "decline": "decline",
    "require_document": "require_document",
}


# ---- Step 1: what the LLM answers, and what code makes of it ----


class Requirement(Strict):
    quote: str = Field(min_length=1)
    summary: str  # the requirement in one full sentence, readable without the text
    outcome: StatedOutcome
    covered_by: str | None  # the current rule that already does exactly this, if any


class RequirementList(Strict):
    requirements: list[Requirement]


@dataclass(frozen=True)
class FoundRequirement:
    number: int  # 1, 2, 3…: how step 2 and the reviewer refer to it
    summary: str
    outcome: StatedOutcome
    covered_by: str | None
    source: Source  # with the real page(s) when the quote was found
    problems: list[str] = field(default_factory=list)

    @property
    def needs_rule(self) -> bool:
        return RULE_OUTCOME[self.outcome] is not None and self.covered_by is None


def check_requirements(
    answer: RequirementList, text: DocumentText, document_name: str, current: Rulebook | None
) -> tuple[list[FoundRequirement], list[str]]:
    """Number the requirements, check each quote is in the text and each covered_by names a
    current rule. Returns them and their problems."""
    current_rules = {rule.name for rule in current.rules} if current else set()
    found = []
    for number, requirement in enumerate(answer.requirements, start=1):
        source, problems = locate_quote(requirement.quote, text, document_name)
        if requirement.covered_by is not None and requirement.covered_by not in current_rules:
            problems.append(f"covered_by: there is no current rule '{requirement.covered_by}'")
        found.append(
            FoundRequirement(
                number,
                requirement.summary,
                requirement.outcome,
                requirement.covered_by,
                source,
                problems,
            )
        )
    problems = [f"requirement {r.number}: {problem}" for r in found for problem in r.problems]
    return found, problems


# ---- Step 2: the rules for the requirements that need one ----


class DraftRule(RuleLogic):
    requirement: int  # the number of the requirement this rule encodes


class DraftRulebook(Strict):
    parameters: list[Parameter]  # first, like AUI: the rules below may only use known ones
    rules: list[DraftRule]


def check_rules(
    draft: DraftRulebook,
    requirements: list[FoundRequirement],
    current: Rulebook | None,
    text: DocumentText,
    document_name: str,
    based_on_version: int | None,
) -> tuple[Proposal, list[str]]:
    """The drafts as a Proposal (with the usual checks, extraction.py), and every problem:
    the proposal's, rules pointing to no requirement or with another outcome than their
    requirement's, and requirements no rule covers."""
    suggested, wrong_numbers = rules_from_drafts(draft, requirements)
    proposal = check_suggestions(suggested, current, text, document_name, based_on_version)
    missed = missed_requirements(draft, requirements)
    proposal = replace(proposal, missed=[describe(r) for r in missed])

    problems = problems_to_fix(proposal) + wrong_numbers + wrong_outcomes(draft, requirements)
    problems += [f"{describe(r)}: no rule written for it" for r in missed]
    return proposal, problems


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


def wrong_outcomes(draft: DraftRulebook, requirements: list[FoundRequirement]) -> list[str]:
    """Rules whose outcome isn't the one their requirement states."""
    by_number = {r.number: r for r in requirements}
    problems = []
    for rule in draft.rules:
        requirement = by_number.get(rule.requirement)
        if requirement is None:
            continue  # already reported by rules_from_drafts
        expected = RULE_OUTCOME[requirement.outcome]
        if rule.outcome != expected:
            problems.append(
                f"rule {rule.name}: its outcome is {rule.outcome}, but requirement "
                f"{requirement.number} says {requirement.outcome} (so the outcome is {expected})"
            )
    return problems


def missed_requirements(
    draft: DraftRulebook, requirements: list[FoundRequirement]
) -> list[FoundRequirement]:
    """Coverage: the requirements that need a rule but have none."""
    covered = {rule.requirement for rule in draft.rules}
    return [r for r in requirements if r.needs_rule and r.number not in covered]


def describe(requirement: FoundRequirement) -> str:
    """ "requirement 3 (page 2): Applicants aged 65 or over are not eligible." """
    page = f" (page {requirement.source.page})" if requirement.source.page else ""
    return f"requirement {requirement.number}{page}: {requirement.summary}"
