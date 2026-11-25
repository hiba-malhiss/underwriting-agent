"""The language model (Azure OpenAI in Foundry), used for STRUCTURED answers only: the reply must
match a pydantic model, so code gets checked data, not free text to parse.

No key: the shared Azure credential gets an Entra token (the identity needs the 'Cognitive
Services OpenAI User' role on the Foundry resource). Temperature 0, so the same input gives the
same answer as far as the model allows.
"""

from typing import TypeVar

from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import get_bearer_token_provider
from openai import APIError, AsyncAzureOpenAI, AuthenticationError, PermissionDeniedError
from pydantic import BaseModel

from app.core.errors import BadGatewayError

AZURE_AI_SCOPE = "https://cognitiveservices.azure.com/.default"
API_VERSION = "2024-10-21"  # supports structured outputs

Output = TypeVar("Output", bound=BaseModel)


class LanguageModelError(BadGatewayError):
    """The model couldn't be reached, refused, or gave no usable answer. Answered with 502, or
    with a message that says what to fix."""

    def public_message(self) -> str:
        return str(self)


class LanguageModel:
    """One shared client for the app's lifetime (opened at startup, closed at shutdown)."""

    def __init__(self, client: AsyncAzureOpenAI, deployment: str):
        self._client = client
        self._deployment = deployment

    @classmethod
    def connect(
        cls, endpoint: str, deployment: str, credential: AsyncTokenCredential
    ) -> "LanguageModel":
        client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=get_bearer_token_provider(credential, AZURE_AI_SCOPE),
            api_version=API_VERSION,
        )
        return cls(client, deployment)

    async def structured(self, system: str, user: str, output: type[Output]) -> Output:
        """Ask the model and get its answer as `output` (strict JSON schema)."""
        try:
            response = await self._client.chat.completions.parse(
                model=self._deployment,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format=output,
            )
        except (AuthenticationError, PermissionDeniedError) as error:
            raise LanguageModelError(
                "Not allowed to use the model. Give your identity the 'Cognitive Services "
                "OpenAI User' role on the Foundry resource (Access control (IAM))."
            ) from error
        except APIError as error:
            raise LanguageModelError(f"The model request failed: {error.message}") from error

        message = response.choices[0].message
        if message.refusal or message.parsed is None:
            raise LanguageModelError("The model gave no usable answer")
        return message.parsed

    async def close(self) -> None:
        await self._client.close()
