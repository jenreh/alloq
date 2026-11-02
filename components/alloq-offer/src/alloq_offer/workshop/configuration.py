"""Configuration of the offer workshop (``app.offer_workshop`` in config.yaml)."""

from typing import Literal

from pydantic import BaseModel, Field, SecretStr

AiProvider = Literal["azure", "demo"]


class AzureOpenAiConfig(BaseModel):
    """Azure OpenAI access; the API key is a secret reference."""

    endpoint: str = ""
    api_key: SecretStr = SecretStr("")
    api_version: str = "2025-04-01-preview"
    chat_deployment: str = ""
    transcription_deployment: str = ""


class WorkshopConfig(BaseModel):
    """Limits, background worker and AI access of the workshop."""

    worker_enabled: bool = False
    # "demo" drafts from source sentences without a language model (local use).
    ai_provider: AiProvider = "azure"
    worker_concurrency: int = Field(default=2, ge=1, le=16)
    poll_interval_seconds: float = Field(default=2.0, gt=0)
    lease_seconds: int = Field(default=300, ge=10)
    max_attempts: int = Field(default=3, ge=1)
    max_blob_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    ai_max_input_chars: int = Field(default=400_000, gt=0)
    ai_timeout_seconds: float = Field(default=300.0, gt=0)
    ai_request_limit: int = Field(default=6, ge=1)
    azure_openai: AzureOpenAiConfig = Field(default_factory=AzureOpenAiConfig)
