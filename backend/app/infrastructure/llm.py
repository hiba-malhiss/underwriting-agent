"""The language model (Azure OpenAI in Foundry), used for STRUCTURED answers only: the reply must
match a pydantic model, so code gets checked data, not free text to parse.

No key: the shared Azure credential gets an Entra token (the identity needs the 'Cognitive
Services OpenAI User' role on the Foundry resource). Temperature 0, so the same input gives the
same answer as far as the model allows.
"""

from dataclasses import dataclass
from typing import Literal, TypeVar

from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import get_bearer_token_provider
from openai import APIError, AsyncAzureOpenAI, AuthenticationError, PermissionDeniedError
from pydantic import BaseModel

from app.core.errors import BadGatewayError

AZURE_AI_SCOPE = "https://cognitiveservices.azure.com/.default"
API_VERSION = "2024-10-21"  # supports structured outputs

Output = TypeVar("Output", bound=BaseModel)


@dataclass(frozen=True)
class Message:
    """One turn of the conversation: what we asked ("user") or what the model answered
    ("assistant"). Earlier turns let the model fix its own answer."""

    role: Literal["user", "assistant"]
    content: str


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

    async def structured(
        self, system: str, messages: list[Message], output: type[Output]
    ) -> Output:
        """Send the conversation and get the model's answer as `output` (strict JSON schema)."""
        try:
            response = await self._client.chat.completions.parse(
                model=self._deployment,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    *({"role": m.role, "content": m.content} for m in messages),
                ],
                response_format=output,
            )
        except (AuthenticationError, PermissionDeniedError) as error:
            raise LanguageModelError(
                "Not allowed to use the model. Give your identity the 'Cognitive Services "
                "OpenAI User' role on the Foundry resource (Access control (IAM))."
            ) from error
        except APIError as error:
            blocked = _content_filters(error.body)
            if blocked:
                raise LanguageModelError(
                    f"Azure's content filter blocked the prompt ({', '.join(blocked)})"
                ) from error
            raise LanguageModelError(f"The model request failed: {error.message}") from error

        message = response.choices[0].message
        if message.refusal or message.parsed is None:
            raise LanguageModelError("The model gave no usable answer")
        return message.parsed

    async def close(self) -> None:
        await self._client.close()


def _content_filters(body: object) -> list[str]:
    """Which of Azure's content filters blocked a prompt, e.g. ["jailbreak"] or ["self_harm"].
    Azure says it in the error body: innererror.content_filter_result → {category: {"filtered":
    true, …}}. Empty when the error isn't a content filter."""
    if not isinstance(body, dict) or body.get("code") != "content_filter":
        return []
    results = (body.get("innererror") or {}).get("content_filter_result") or {}
    blocked = [
        name
        for name, result in results.items()
        if isinstance(result, dict) and result.get("filtered")
    ]
    return blocked or ["no category given"]
