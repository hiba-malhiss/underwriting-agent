"""Starting an indexer, with a fake Azure client: which answers count as fine and which fail."""

import asyncio

import pytest
from azure.core.exceptions import HttpResponseError

from app.infrastructure.search.exceptions import SearchError
from app.infrastructure.search.indexer import IndexerRunner


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.reason = "fake"
        self.headers = {}

    def text(self, encoding=None):
        return ""


class FakeClient:
    def __init__(self, status_code=None):
        self.status_code = status_code
        self.started: list[str] = []

    async def run_indexer(self, name):
        self.started.append(name)
        if self.status_code:
            raise HttpResponseError(response=FakeResponse(self.status_code))


def test_run_starts_the_indexer():
    client = FakeClient()
    asyncio.run(IndexerRunner(client, "requirements-indexer").run())
    assert client.started == ["requirements-indexer"]


# 409 = already running: that run picks the change up, so it isn't an error
def test_already_running_is_fine():
    asyncio.run(IndexerRunner(FakeClient(409), "requirements-indexer").run())


# A missing role says which role to add
def test_forbidden_says_which_role_is_missing():
    with pytest.raises(SearchError, match="Search Service Contributor"):
        asyncio.run(IndexerRunner(FakeClient(403), "requirements-indexer").run())
