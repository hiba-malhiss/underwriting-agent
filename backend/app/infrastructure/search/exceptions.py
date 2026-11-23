"""AI Search errors: the app's own exceptions, and how Azure SDK errors map onto them.

Short messages that say what to fix. They are AppErrors, so core/error_handlers.py can answer
them if a caller lets them through.
"""

from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

from app.core.errors import BadGatewayError


class SearchError(BadGatewayError):
    """AI Search couldn't be reached or refused the request."""

    def public_message(self) -> str:
        return "Search request failed"


def to_search_error(error: HttpResponseError, indexer_name: str) -> SearchError:
    if isinstance(error, ClientAuthenticationError) or error.status_code == 403:
        return SearchError(
            f"Not allowed to run indexer '{indexer_name}'. Give your identity the "
            "'Search Service Contributor' role on the search service (Access control (IAM))."
        )
    if error.status_code == 404:
        return SearchError(
            f"Indexer '{indexer_name}' not found. Check the indexer name in .env "
            "(AI Search → Indexers)."
        )
    return SearchError(str(error))
