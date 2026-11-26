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
from app.rules.domain.models import Rulebook
from app.rules.domain.validation import ensure_valid
from app.rules.generation.extraction import Proposal
from app.rules.generation.parameter_checks import merge_parameters
from app.rules.generation.prompts import (
    REQUIREMENTS_PROMPT,
    RULES_PROMPT,
    build_requirements_prompt,
    build_rules_prompt,
)
from app.rules.generation.repair import ask_with_repairs
from app.rules.generation.requirements import (
    DraftRulebook,
    FoundRequirement,
    RequirementList,
    check_requirements,
    check_rules,
)
from app.rules.persistence.repository import RulebookRepository, RulebookVersion


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
        # 1. The document and the current rulebook
        text = await self._load_document(document_name)
        current = await self._repository.get_current()

        # 2. What the guidelines require (step 1)
        requirements, repairs_1 = await self._extract_requirements(document_name, text, current)

        # 3. The rules for those requirements (step 2)
        proposal, repairs_2 = await self._generate_rules(requirements, document_name, text, current)

        return replace(proposal, repair_rounds=repairs_1 + repairs_2)

    async def _load_document(self, document_name: str) -> DocumentText:
        data = await self._guideline_file.download(document_name)
        return await self._reader.read(data)

    async def _extract_requirements(
        self, document_name: str, text: DocumentText, current: RulebookVersion | None
    ) -> tuple[list[FoundRequirement], int]:
        """Every requirement in the text, each quote checked (and fixed by the model if needed)."""
        prompt = build_requirements_prompt(document_name, text, _rulebook(current))
        return await ask_with_repairs(
            self._model,
            REQUIREMENTS_PROMPT,
            prompt,
            RequirementList,
            check=lambda answer: check_requirements(
                answer, text, document_name, _rulebook(current)
            ),
        )

    async def _generate_rules(
        self,
        requirements: list[FoundRequirement],
        document_name: str,
        text: DocumentText,
        current: RulebookVersion | None,
    ) -> tuple[Proposal, int]:
        """The parameters and rules for the requirements that need one, checked, and every one of
        those requirements covered by a rule."""
        to_add = [r for r in requirements if r.needs_rule]
        version = current.version if current else None

        def check(draft: DraftRulebook):
            return check_rules(draft, to_add, _rulebook(current), text, document_name, version)

        if not to_add:  # nothing new in the document: no need to ask
            proposal, _ = check(DraftRulebook(parameters=[], rules=[]))
            return proposal, 0

        prompt = build_rules_prompt(to_add, _rulebook(current))
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


def _rulebook(current: RulebookVersion | None) -> Rulebook | None:
    return current.rulebook if current else None
