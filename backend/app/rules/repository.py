"""Saves and reads rulebook versions (like a Spring @Repository): the only place with SQL for
rules. Services get and give `Rulebook` (models.py), never table rows.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError
from app.rules.models import Rulebook
from app.rules.tables import ParameterRow, RulebookVersionRow, RuleRow


@dataclass(frozen=True)
class RulebookVersion:
    version: int  # 1, 2, 3… (not the row's id)
    approved_at: datetime  # UTC
    note: str | None
    rulebook: Rulebook


class RulebookVersionConflictError(ConflictError):
    """Two saves at the same moment got the same version. Answered with 409; saving again
    gives the next version."""


class RulebookRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]):
        self._sessions = sessions

    async def save_new_version(
        self, rulebook: Rulebook, note: str | None = None
    ) -> RulebookVersion:
        """Save the whole rulebook as the next version (1 if there's none yet)."""
        try:
            async with self._sessions.begin() as session:
                latest = await session.scalar(select(func.max(RulebookVersionRow.version)))
                row = _to_row(rulebook, (latest or 0) + 1, note)
                session.add(row)
        except IntegrityError as error:  # the unique version: someone saved at the same moment
            raise RulebookVersionConflictError(
                "Another version was saved at the same time; save again"
            ) from error
        return _to_version(row)

    async def get_current(self) -> RulebookVersion | None:
        """The newest version, or None before the first save."""
        query = _with_children(select(RulebookVersionRow)).order_by(
            RulebookVersionRow.version.desc()
        )
        async with self._sessions() as session:
            row = await session.scalar(query.limit(1))
        return _to_version(row) if row else None

    async def get_version(self, version: int) -> RulebookVersion | None:
        query = _with_children(select(RulebookVersionRow)).where(
            RulebookVersionRow.version == version
        )
        async with self._sessions() as session:
            row = await session.scalar(query)
        return _to_version(row) if row else None


def _with_children(query):
    # Load parameters and rules in the same session (async can't load them lazily later)
    return query.options(
        selectinload(RulebookVersionRow.parameters), selectinload(RulebookVersionRow.rules)
    )


def _to_row(rulebook: Rulebook, version: int, note: str | None) -> RulebookVersionRow:
    return RulebookVersionRow(
        version=version,
        approved_at=datetime.now(UTC).replace(tzinfo=None),  # stored as UTC
        note=note,
        parameters=[
            ParameterRow(
                name=p.name,
                value_type=p.value_type,
                description=p.description,
                allowed_values=p.allowed_values,
                unit=p.unit,
            )
            for p in rulebook.parameters
        ],
        rules=[
            RuleRow(
                name=r.name,
                description=r.description,
                rule_type=r.rule_type,
                conditions=(
                    r.conditions.model_dump(mode="json", exclude_none=True)
                    if r.conditions
                    else None
                ),
                outcome=r.outcome,
                source=r.source.model_dump(mode="json"),
            )
            for r in rulebook.rules
        ],
    )


def _to_version(row: RulebookVersionRow) -> RulebookVersion:
    # Back through the pydantic models, so a stored rulebook is checked like a new one
    rulebook = Rulebook.model_validate(
        {
            "parameters": [
                {
                    "name": p.name,
                    "value_type": p.value_type,
                    "description": p.description,
                    "allowed_values": p.allowed_values,
                    "unit": p.unit,
                }
                for p in row.parameters
            ],
            "rules": [
                {
                    "name": r.name,
                    "description": r.description,
                    "rule_type": r.rule_type,
                    "conditions": r.conditions,
                    "outcome": r.outcome,
                    "source": r.source,
                }
                for r in row.rules
            ],
        }
    )
    return RulebookVersion(row.version, row.approved_at.replace(tzinfo=UTC), row.note, rulebook)
