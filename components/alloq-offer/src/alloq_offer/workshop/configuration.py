"""Configuration of the offer workshop (``app.offer_workshop`` in config.yaml)."""

from pydantic import BaseModel, Field, SecretStr


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
    worker_concurrency: int = Field(default=2, ge=1, le=16)
    poll_interval_seconds: float = Field(default=2.0, gt=0)
    lease_seconds: int = Field(default=300, ge=10)
    max_attempts: int = Field(default=3, ge=1)
    max_blob_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    azure_openai: AzureOpenAiConfig = Field(default_factory=AzureOpenAiConfig)
