"""The rulebook's MySQL tables. One saved rulebook = one version row + its parameters and rules.

Versions are never edited: saving creates a new row with the next version, so old versions
stay as they were and every evaluation can say which version it used. The parts whose
shape varies (conditions, allowed values, rule sources) are JSON columns; the code reads them back
through models.py, which checks their shape.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class RulebookVersionRow(Base):
    __tablename__ = "rulebook_versions"

    id: Mapped[int] = mapped_column(primary_key=True)  # internal key, for the foreign keys
    # The version users see: 1, 2, 3… with no gaps. Unique, so two saves at the same moment
    # can't both become the same version
    version: Mapped[int] = mapped_column(unique=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime)  # UTC
    note: Mapped[str | None] = mapped_column(Text)

    parameters: Mapped[list["ParameterRow"]] = relationship(
        cascade="all, delete-orphan", order_by="ParameterRow.id"
    )
    rules: Mapped[list["RuleRow"]] = relationship(
        cascade="all, delete-orphan", order_by="RuleRow.id"
    )


class ParameterRow(Base):
    __tablename__ = "parameters"
    __table_args__ = (UniqueConstraint("rulebook_version_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rulebook_version_id: Mapped[int] = mapped_column(
        ForeignKey("rulebook_versions.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(100))
    value_type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    allowed_values: Mapped[list[str] | None] = mapped_column(JSON)
    unit: Mapped[str | None] = mapped_column(String(50))


class RuleRow(Base):
    __tablename__ = "rules"
    __table_args__ = (UniqueConstraint("rulebook_version_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rulebook_version_id: Mapped[int] = mapped_column(
        ForeignKey("rulebook_versions.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    rule_type: Mapped[str] = mapped_column(String(20))
    conditions: Mapped[dict | None] = mapped_column(JSON)
    outcome: Mapped[str] = mapped_column(String(30))
    source: Mapped[dict] = mapped_column(JSON)
