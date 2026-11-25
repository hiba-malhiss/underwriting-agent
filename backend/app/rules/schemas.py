"""The rules API's request and response bodies. The rulebook shapes themselves (Parameter, Rule)
come from models.py, so the API, the LLM and the database all use the same format."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel

from app.rules.extraction import Proposal
from app.rules.models import Parameter, Rule
from app.rules.repository import RulebookVersion


class ProposeRequest(BaseModel):
    document: str  # the guideline file's stored name (from the documents list)


class SuggestedParameterResponse(BaseModel):
    parameter: Parameter
    problems: list[str]


class SuggestedRuleResponse(BaseModel):
    rule: Rule
    problems: list[str]


class ProposalResponse(BaseModel):
    based_on_version: int | None
    document: str
    parameters: list[SuggestedParameterResponse]
    rules: list[SuggestedRuleResponse]
    skipped: list[str]

    @classmethod
    def from_proposal(cls, proposal: Proposal) -> Self:
        return cls(
            based_on_version=proposal.based_on_version,
            document=proposal.document,
            parameters=[
                SuggestedParameterResponse(parameter=s.parameter, problems=s.problems)
                for s in proposal.parameters
            ],
            rules=[SuggestedRuleResponse(rule=s.rule, problems=s.problems) for s in proposal.rules],
            skipped=proposal.skipped,
        )


class SaveVersionRequest(BaseModel):
    """The additions a human approved, and the version the proposal was based on."""

    based_on_version: int | None
    parameters: list[Parameter]
    rules: list[Rule]
    note: str | None = None


class RulebookVersionResponse(BaseModel):
    version: int
    approved_at: datetime
    note: str | None
    parameters: list[Parameter]
    rules: list[Rule]

    @classmethod
    def from_version(cls, version: RulebookVersion) -> Self:
        return cls(
            version=version.version,
            approved_at=version.approved_at,
            note=version.note,
            parameters=version.rulebook.parameters,
            rules=version.rulebook.rules,
        )
