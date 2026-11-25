"""Rules service: the business steps for the rulebook (like a Spring @Service).

- propose_from_guideline: a guideline file → read it → step 1: the LLM lists what it requires
  → step 2: the LLM writes the parameters and rules for it → checks (requirements.py,
  extraction.py), each step with the repair loop (repair.py) → a Proposal. Nothing is saved: a
  human approves first.
- save_additions: the additions a human approved → version N+1 = all current rules + them.
  Nothing is removed or changed, and it's refused if the rules changed since the proposal.

Plain Python on purpose: no FastAPI. Its parts are passed in, so tests give it fakes.
"""

from dataclasses import replace

from app.core.errors import ConflictError
from app.infrastructure.document_reader import DocumentReader, DocumentText
from app.infrastructure.llm import LanguageModel
from app.infrastructure.storage.blob import BlobStore
from app.rules.extraction import Proposal, check_suggestions
from app.rules.models import Rulebook
from app.rules.parameter_checks import merge_parameters
from app.rules.prompts import (
    REQUIREMENTS_PROMPT,
    RULES_PROMPT,
    build_requirements_prompt,
    build_rules_prompt,
)
from app.rules.repair import ask_with_repairs, problems_to_fix
from app.rules.repository import RulebookRepository, RulebookVersion
from app.rules.requirements import (
    DraftRulebook,
    FoundRequirement,
    RequirementList,
    check_requirements,
    describe,
    missed_requirements,
    requirement_problems,
    rules_from_drafts,
)
from app.rules.validation import ensure_valid


class RulesChangedError(ConflictError):
    """Another version was saved after the proposal was made. Answered with 409."""


class RulesService:
    def __init__(
        self,
        guideline_file: BlobStore,
        reader: DocumentReader,
        model: LanguageModel,
        repository: RulebookRepository,
    ):
        self._guideline_file = guideline_file
        self._reader = reader
        self._model = model
        self._repository = repository

    async def propose_from_guideline(self, document_name: str) -> Proposal:
        data = await self._guideline_file.download(document_name)
        text = await self._reader.read(data)
        current = await self._repository.get_current()
        current_rulebook = current.rulebook if current else None

        requirements, repairs_1 = await self._find_requirements(
            text, document_name, current_rulebook
        )
        to_add = [r for r in requirements if r.action == "add_rule"]
        proposal, repairs_2 = await self._write_rules(
            to_add, text, document_name, current_rulebook, current.version if current else None
        )
        return replace(proposal, repair_rounds=repairs_1 + repairs_2)

    async def _find_requirements(
        self, text: DocumentText, document_name: str, current: Rulebook | None
    ) -> tuple[list[FoundRequirement], int]:
        """Step 1: what the guidelines require, each quote checked."""

        def check(answer: RequirementList):
            found = check_requirements(answer, text, document_name)
            return found, requirement_problems(found)

        prompt = build_requirements_prompt(document_name, text, current)
        return await ask_with_repairs(
            self._model, REQUIREMENTS_PROMPT, prompt, RequirementList, check
        )

    async def _write_rules(
        self,
        requirements: list[FoundRequirement],
        text: DocumentText,
        document_name: str,
        current: Rulebook | None,
        based_on_version: int | None,
    ) -> tuple[Proposal, int]:
        """Step 2: the parameters and rules for the requirements, checked, and every
        requirement covered by a rule."""
        if not requirements:  # nothing new in the document: no need to ask
            empty = Rulebook(parameters=[], rules=[])
            return check_suggestions(empty, current, text, document_name, based_on_version), 0

        def check(draft: DraftRulebook):
            suggested, wrong_numbers = rules_from_drafts(draft, requirements)
            proposal = check_suggestions(suggested, current, text, document_name, based_on_version)
            missed = missed_requirements(draft, requirements)
            proposal = replace(proposal, missed=[describe(r) for r in missed])
            problems = problems_to_fix(proposal) + wrong_numbers
            problems += [f"{describe(r)}: no rule written for it" for r in missed]
            return proposal, problems

        prompt = build_rules_prompt(requirements, current)
        return await ask_with_repairs(self._model, RULES_PROMPT, prompt, DraftRulebook, check)

    async def get_current(self) -> RulebookVersion | None:
        return await self._repository.get_current()

    async def save_additions(
        self, additions: Rulebook, based_on_version: int | None, note: str | None = None
    ) -> RulebookVersion:
        """Save version N+1 = the current rules + the approved additions. Refused (409) if a newer
        version was saved since the proposal, and (400) if the result doesn't pass the checks."""
        current = await self._repository.get_current()
        if (current.version if current else None) != based_on_version:
            raise RulesChangedError(
                "The rules changed since this suggestion was made; suggest again"
            )
        base = current.rulebook if current else Rulebook(parameters=[], rules=[])
        combined = Rulebook(
            parameters=merge_parameters(base.parameters, additions.parameters),
            rules=base.rules + additions.rules,
        )
        ensure_valid(combined)
        return await self._repository.save_new_version(combined, note)
