"""The one Azure identity the app signs in with, shared by every Azure client.

- On Azure: DefaultAzureCredential, which finds the app's Managed Identity. No secret anywhere.
- On a laptop (AZURE_INTERACTIVE_LOGIN=true): a browser sign-in with your own Azure account.

Why an adapter: the app uses the async Azure clients, and the async `azure-identity` has no
browser sign-in (InteractiveBrowserCredential exists only in the sync package). So the sync
credential is wrapped and run in a worker thread. It caches the token after the first sign-in
and refreshes it silently, so the browser opens once per app start.

Never enable the browser sign-in on a server: there is nobody there to click "Sign in".
"""

import asyncio
from typing import Any

from azure.core.credentials import AccessToken
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity import InteractiveBrowserCredential
from azure.identity.aio import DefaultAzureCredential


class BrowserLoginCredential(AsyncTokenCredential):
    """The sync browser sign-in, usable by the async Azure clients."""

    def __init__(self, tenant_id: str | None = None):
        # A personal (e.g. Gmail-based) account must sign in to its own tenant, so pass it
        self._credential = InteractiveBrowserCredential(tenant_id=tenant_id)
        # Concurrent first requests share one sign-in instead of opening several browser tabs
        self._lock = asyncio.Lock()

    async def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        async with self._lock:
            return await asyncio.to_thread(self._credential.get_token, *scopes, **kwargs)

    async def close(self) -> None:
        self._credential.close()


def azure_credential(interactive: bool, tenant_id: str | None = None) -> AsyncTokenCredential:
    """The credential for this environment: browser sign-in locally, else the default chain."""
    if interactive:
        return BrowserLoginCredential(tenant_id)
    return DefaultAzureCredential()
