"""Saving approved additions (the service) and the /rules routes, with fakes instead of Azure."""

import asyncio
import os
from datetime import UTC, datetime

os.environ.setdefault("AZURE_STORAGE_ACCOUNT_URL", "https://example.blob.core.windows.net")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.rules.dependencies import get_rules_service  # noqa: E402
from app.rules.domain.models import Rulebook  # noqa: E402
from app.rules.domain.validation import RulebookInvalidError  # noqa: E402
from app.rules.persistence.repository import RulebookVersion  # noqa: E402
from app.rules.service import RulesChangedError, RulesService  # noqa: E402
from tests.rules.sample import sample_rulebook, source  # noqa: E402

NEW_RULE = {
    "name": "very_high_bmi",
    "description": "BMI above 45 is not eligible",
    "rule_type": "automatic",
    "conditions": {
        "match": "all",
        "items": [{"parameter": "bmi", "operator": "greater_than", "value": 45}],
    },
    "outcome": "decline",
    "source": source("A BMI above 45 is not eligible", 3),
}


class FakeRepository:
    """Version 1 = the sample rulebook; saving makes the next version."""

    def __init__(self, current: Rulebook | None):
        self.versions = [current] if current else []

    async def get_current(self):
        if not self.versions:
            return None
        return RulebookVersion(len(self.versions), datetime.now(UTC), None, self.versions[-1])

    async def save_new_version(self, rulebook, note=None):
        self.versions.append(rulebook)
        return RulebookVersion(len(self.versions), datetime.now(UTC), note, rulebook)


def service_with(current: Rulebook | None) -> tuple[RulesService, FakeRepository]:
    repository = FakeRepository(current)
    return RulesService(None, None, None, repository), repository


def additions(rules: list[dict]) -> Rulebook:
    return Rulebook.model_validate({"parameters": [], "rules": rules})


# Version N+1 = everything in version N + the approved additions; nothing removed or changed
def test_saving_keeps_the_current_rules_and_adds_the_approved_ones():
    service, repository = service_with(sample_rulebook())

    saved = asyncio.run(service.save_additions(additions([NEW_RULE]), based_on_version=1))

    assert saved.version == 2
    names = [r.name for r in saved.rulebook.rules]
    assert names == [r.name for r in sample_rulebook().rules] + ["very_high_bmi"]
    assert repository.versions[0] == sample_rulebook()  # version 1 untouched


# A suggestion made before someone else saved can't overwrite the newer rules
def test_saving_is_refused_if_the_rules_changed_since_the_proposal():
    service, _ = service_with(sample_rulebook())
    with pytest.raises(RulesChangedError):
        asyncio.run(service.save_additions(additions([NEW_RULE]), based_on_version=None))


# The combined rulebook must pass the checks (e.g. no unknown parameters)
def test_saving_is_refused_if_the_result_is_invalid():
    broken = {
        **NEW_RULE,
        "conditions": {
            "match": "all",
            "items": [{"parameter": "weight", "operator": "greater_than", "value": 1}],
        },
    }
    service, repository = service_with(sample_rulebook())
    with pytest.raises(RulebookInvalidError):
        asyncio.run(service.save_additions(additions([broken]), based_on_version=1))
    assert len(repository.versions) == 1  # nothing saved


# ---- Routes (the service replaced by one with a fake repository) ----


@pytest.fixture
def client():
    service, _ = service_with(sample_rulebook())
    app.dependency_overrides = {get_rules_service: lambda: service}
    yield TestClient(app)
    app.dependency_overrides = {}


def test_get_current_returns_the_newest_version(client):
    body = client.get("/rules/current").json()
    assert body["version"] == 1
    assert [r["name"] for r in body["rules"]][0] == "max_age"


def test_post_versions_saves_and_answers_201(client):
    response = client.post(
        "/rules/versions",
        json={"based_on_version": 1, "parameters": [], "rules": [NEW_RULE], "note": "BMI"},
    )
    assert response.status_code == 201
    assert response.json()["version"] == 2


def test_post_versions_answers_409_when_the_rules_changed(client):
    response = client.post(
        "/rules/versions", json={"based_on_version": 7, "parameters": [], "rules": [NEW_RULE]}
    )
    assert response.status_code == 409
    assert "suggest again" in response.json()["detail"]
