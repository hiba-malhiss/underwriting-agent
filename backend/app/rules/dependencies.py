"""Wiring for the rules module (dependency injection), like documents/dependencies.py.

- At startup, main.py creates the shared clients once and keeps them in app.state: the MySQL
  engine and its session factory, the document reader, the language model, the blob stores.
- Per request, Depends builds the repository and the service from them. Both are cheap (they
  hold no connection of their own), so controllers just declare them:

      service: Annotated[RulesService, Depends(get_rules_service)]

A part that isn't configured in .env answers 503 with what to set.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ServiceUnavailableError
from app.documents.dependencies import get_stores
from app.documents.types import DocumentType
from app.infrastructure.document_reader import DocumentReader
from app.infrastructure.llm import LanguageModel
from app.infrastructure.storage.blob import BlobStore
from app.rules.persistence.repository import RulebookRepository
from app.rules.service import RulesService


class NotConfiguredError(ServiceUnavailableError):
    """A service the request needs isn't set up in .env. Answered with 503 and what to set."""

    def public_message(self) -> str:
        return str(self)


def get_db_sessions(request: Request) -> async_sessionmaker[AsyncSession]:
    sessions = request.app.state.db_sessions
    if sessions is None:
        raise NotConfiguredError(
            "The database isn't configured. Set MYSQL_HOST and MYSQL_USER in .env."
        )
    return sessions


def get_document_reader(request: Request) -> DocumentReader:
    reader = request.app.state.document_reader
    if reader is None:
        raise NotConfiguredError(
            "Document Intelligence isn't configured. Set DOCUMENT_INTELLIGENCE_ENDPOINT in .env."
        )
    return reader


def get_language_model(request: Request) -> LanguageModel:
    model = request.app.state.language_model
    if model is None:
        raise NotConfiguredError(
            "The language model isn't configured. Set AZURE_OPENAI_ENDPOINT in .env."
        )
    return model


def get_rulebook_repository(
    sessions: Annotated[async_sessionmaker[AsyncSession], Depends(get_db_sessions)],
) -> RulebookRepository:
    return RulebookRepository(sessions)


def get_rules_service(
    stores: Annotated[dict[DocumentType, BlobStore], Depends(get_stores)],
    reader: Annotated[DocumentReader, Depends(get_document_reader)],
    model: Annotated[LanguageModel, Depends(get_language_model)],
    repository: Annotated[RulebookRepository, Depends(get_rulebook_repository)],
) -> RulesService:
    # Guidelines are the "requirement" documents' container
    return RulesService(stores[DocumentType.REQUIREMENT], reader, model, repository)
