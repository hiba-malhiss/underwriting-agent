"""Azure AI Search indexers: start one on demand, so a changed document is searchable soon.

An indexer copies a container into a search index (split into chunks, turned into vectors). It
also runs on its own schedule (set in the Portal); running it right after an upload or delete
makes the change searchable in about a minute instead of within the hour. The schedule stays as
the safety net for anything this misses.
"""

from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError, HttpResponseError
from azure.search.documents.indexes.aio import SearchIndexerClient

from app.infrastructure.search.exceptions import SearchError, to_search_error


class IndexerRunner:
    """Starts one indexer. One shared client for the app's lifetime."""

    def __init__(self, client: SearchIndexerClient, indexer_name: str):
        self._client = client
        self._indexer_name = indexer_name

    @classmethod
    def connect(
        cls, endpoint: str, indexer_name: str, credential: AsyncTokenCredential
    ) -> "IndexerRunner":
        """The identity needs the 'Search Service Contributor' role on the search service:
        'Search Index Data Reader' can search, but not run indexers."""
        return cls(SearchIndexerClient(endpoint, credential), indexer_name)

    async def run(self) -> None:
        try:
            await self._client.run_indexer(self._indexer_name)
        except HttpResponseError as error:
            # 409: it's already running. That run (or the next scheduled one) picks the change up
            if error.status_code == 409:
                return
            raise to_search_error(error, self._indexer_name) from error
        except AzureError as error:
            raise SearchError(str(error)) from error

    async def close(self) -> None:
        await self._client.close()
