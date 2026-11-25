"""Rules service: the business steps for the rulebook (like a Spring @Service).

- propose_from_guideline: a guideline file → read it → the LLM suggests additions to the current
  version → checks (extraction.py) → a Proposal. Nothing is saved: a human approves first.
- save_additions: the additions a human approved → version N+1 = all current rules + them.
  Nothing is removed or changed, and it's refused if the rules changed since the proposal.

Plain Python on purpose: no FastAPI. Its parts are passed in, so tests give it fakes.
"""

from app.core.errors import ConflictError
from app.infrastructure.document_reader import DocumentReader
from app.infrastructure.llm import LanguageModel
from app.infrastructure.storage.blob import BlobStore
from app.rules.extraction import Proposal, check_suggestions
from app.rules.models import Rulebook
from app.rules.parameter_checks import merge_parameters
from app.rules.prompts import SYSTEM_PROMPT, build_user_prompt
from app.rules.repository import RulebookRepository, RulebookVersion
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

        suggested = await self._model.structured(
            SYSTEM_PROMPT, build_user_prompt(document_name, text, current_rulebook), Rulebook
        )
        return check_suggestions(
            suggested,
            current_rulebook,
            text,
            document_name,
            based_on_version=current.version if current else None,
        )

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
