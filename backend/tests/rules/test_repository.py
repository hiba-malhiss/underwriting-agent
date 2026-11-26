"""Saving and reading rulebook versions, on an in-memory SQLite database (same tables and code
as MySQL, no Azure): versions count up, old versions never change, data comes back as saved."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.database import create_sessions, create_tables
from app.rules.domain.models import Rulebook
from app.rules.persistence.repository import RulebookRepository
from tests.rules.sample import sample_rulebook


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.fixture
def repository():
    async def setup():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        await create_tables(engine)
        return engine, RulebookRepository(create_sessions(engine))

    engine, repo = run(setup())
    yield repo
    run(engine.dispose())


def test_no_current_version_before_the_first_save(repository):
    assert run(repository.get_current()) is None


# What comes back is exactly what was saved (nested conditions, sources, allowed values)
def test_a_saved_rulebook_comes_back_the_same(repository):
    saved = run(repository.save_new_version(sample_rulebook(), note="first guidelines"))
    current = run(repository.get_current())

    assert (saved.version, current.version) == (1, 1)
    assert current.note == "first guidelines"
    assert current.rulebook == sample_rulebook()


# Saving again creates the next version; the old one stays as it was
def test_each_save_is_a_new_version_and_old_ones_never_change(repository):
    first = sample_rulebook()
    second = Rulebook.model_validate(
        {**first.model_dump(), "rules": first.model_dump()["rules"][:1]}  # only max_age
    )

    run(repository.save_new_version(first))
    run(repository.save_new_version(second))

    assert run(repository.get_current()).version == 2
    assert run(repository.get_current()).rulebook == second
    assert run(repository.get_version(1)).rulebook == first
    assert run(repository.get_version(3)) is None
