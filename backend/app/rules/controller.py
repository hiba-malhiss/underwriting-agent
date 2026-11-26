"""Rules controller: the HTTP layer for the rulebook (like a Spring @RestController).

    GET  /rules/current     the current version (null before the first save)
    POST /rules/proposals   {"document": "<guideline file>"} → suggested additions (not saved)
    POST /rules/versions    the approved additions → version N+1 = current rules + them

Only HTTP here; the steps are in service.py. Errors are raised, not caught: core/error_handlers.py
answers them (400 with the problems, 409 if the rules changed since the proposal, 503 if a
service isn't configured).

No authentication yet: keep this API local (don't expose it) until access control is added.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.rules.dependencies import get_rules_service
from app.rules.domain.models import Rulebook
from app.rules.schemas import (
    ProposalResponse,
    ProposeRequest,
    RulebookVersionResponse,
    SaveVersionRequest,
)
from app.rules.service import RulesService

router = APIRouter(prefix="/rules", tags=["Rules"])

Service = Annotated[RulesService, Depends(get_rules_service)]


@router.get("/current", response_model=RulebookVersionResponse | None)
async def get_current(service: Service) -> RulebookVersionResponse | None:
    current = await service.get_current()
    return RulebookVersionResponse.from_version(current) if current else None


@router.post("/proposals", response_model=ProposalResponse)
async def propose(body: ProposeRequest, service: Service) -> ProposalResponse:
    """Can take 1–2 minutes: the document is read, then the LLM lists its requirements and
    writes rules for them (each step fixed by the model if the checks find problems)."""
    proposal = await service.propose_from_guideline(body.document)
    return ProposalResponse.from_proposal(proposal)


@router.post(
    "/versions", response_model=RulebookVersionResponse, status_code=status.HTTP_201_CREATED
)
async def save_version(body: SaveVersionRequest, service: Service) -> RulebookVersionResponse:
    additions = Rulebook(parameters=body.parameters, rules=body.rules)
    version = await service.save_additions(additions, body.based_on_version, body.note)
    return RulebookVersionResponse.from_version(version)
