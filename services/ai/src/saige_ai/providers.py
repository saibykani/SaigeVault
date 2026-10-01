"""Provider protocols and value types."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable


class ProviderLocality(StrEnum):
    """Where document content goes when this provider is used."""

    LOCAL = "local"  # Runs inside the deployment (e.g. Ollama, Tesseract).
    THIRD_PARTY = "third_party"  # Content is sent to an external service.


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    model: str
    usage: Usage = field(default_factory=Usage)
    stop_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CompletionChunk:
    delta: str
    usage: Usage | None = None
    done: bool = False


@dataclass(frozen=True, slots=True)
class RerankResult:
    index: int
    score: float


@dataclass(frozen=True, slots=True)
class OCRWord:
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class OCRPage:
    page_number: int
    text: str
    words: Sequence[OCRWord] = ()
    confidence: float | None = None


@runtime_checkable
class Provider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def locality(self) -> ProviderLocality: ...


@runtime_checkable
class LLMProvider(Provider, Protocol):
    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int,
        temperature: float = 0.0,
    ) -> Completion: ...

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int,
        temperature: float = 0.0,
    ) -> AsyncIterator[CompletionChunk]: ...


@runtime_checkable
class EmbeddingProvider(Provider, Protocol):
    @property
    def model(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


@runtime_checkable
class RerankerProvider(Provider, Protocol):
    async def rerank(
        self, query: str, documents: Sequence[str], *, top_k: int
    ) -> list[RerankResult]: ...


@runtime_checkable
class OCRProvider(Provider, Protocol):
    async def recognize(self, image: bytes, *, page_number: int = 1) -> OCRPage: ...
