"""Rules service: the business steps for the rulebook (like a Spring @Service).

propose_from_guideline: a guideline file → read it → the LLM suggests additions to the current
version → checks (extraction.py) → a Proposal. Nothing is saved: a human approves first.

Plain Python on purpose: no FastAPI. Its parts are passed in, so tests give it fakes.
"""

from app.infrastructure.document_reader import DocumentReader
from app.infrastructure.llm import LanguageModel
from app.infrastructure.storage.blob import BlobStore
from app.rules.extraction import Proposal, check_suggestions
from app.rules.models import Rulebook
from app.rules.prompts import SYSTEM_PROMPT, build_user_prompt
from app.rules.repository import RulebookRepository


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
