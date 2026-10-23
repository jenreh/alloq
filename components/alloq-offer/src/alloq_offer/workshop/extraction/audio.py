"""Audio recordings: a transcriber port and its Azure OpenAI adapter."""

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from alloq_offer.workshop.configuration import AzureOpenAiConfig
from alloq_offer.workshop.extraction.models import (
    KIND_SPEECH,
    ExtractedBlock,
    ExtractionResult,
)

logger = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 25 * 1024 * 1024
AUDIO_TOO_LARGE = (
    "Die Aufnahme ist für die automatische Transkription zu groß. "
    "Bitte laden Sie ein Transkript als Text hoch."
)
NO_TRANSCRIBER = "Für Aufnahmen ist keine Transkription eingerichtet."
REQUEST_TIMEOUT_SECONDS = 600.0


class TranscriptionUnavailableError(RuntimeError):
    """The file cannot be transcribed here; the user has to upload a transcript."""


@dataclass(frozen=True)
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None


class Transcriber(Protocol):
    async def transcribe(
        self, data: bytes, filename: str, mime: str
    ) -> list[TranscriptSegment]: ...


def to_result(segments: list[TranscriptSegment]) -> ExtractionResult:
    """Blocks with technical speaker labels (``Sprecher 1``), never identities."""
    labels: dict[str, str] = {}
    blocks: list[ExtractedBlock] = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        speaker = None
        if segment.speaker:
            speaker = labels.setdefault(segment.speaker, f"Sprecher {len(labels) + 1}")
        blocks.append(
            ExtractedBlock(
                KIND_SPEECH,
                text,
                {"start_ms": segment.start_ms, "end_ms": segment.end_ms},
                speaker,
            )
        )
    return ExtractionResult(blocks=blocks)


def _segments(payload: dict) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(
            start_ms=round(float(item.get("start", 0)) * 1000),
            end_ms=round(float(item.get("end", 0)) * 1000),
            text=str(item.get("text", "")),
            speaker=item.get("speaker"),
        )
        for item in payload.get("segments", [])
    ]


class AzureTranscriber:
    """Transcription through an Azure OpenAI deployment.

    A ``diarize`` deployment returns speaker segments (``diarized_json``); any other
    deployment returns timed segments without speakers (``verbose_json``).
    """

    def __init__(self, config: AzureOpenAiConfig) -> None:
        self._config = config

    @property
    def configured(self) -> bool:
        return bool(self._config.endpoint and self._config.transcription_deployment)

    async def transcribe(
        self, data: bytes, filename: str, mime: str
    ) -> list[TranscriptSegment]:
        if not self.configured:
            raise TranscriptionUnavailableError(NO_TRANSCRIBER)
        if len(data) > MAX_AUDIO_BYTES:
            raise TranscriptionUnavailableError(AUDIO_TOO_LARGE)
        deployment = self._config.transcription_deployment
        diarized = "diarize" in deployment
        form = {"response_format": "diarized_json" if diarized else "verbose_json"}
        if diarized:
            form["chunking_strategy"] = "auto"
        url = (
            f"{self._config.endpoint.rstrip('/')}/openai/deployments/{deployment}"
            "/audio/transcriptions"
        )
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                params={"api-version": self._config.api_version},
                headers={"api-key": self._config.api_key.get_secret_value()},
                data=form,
                files={"file": (filename, data, mime)},
            )
        response.raise_for_status()
        logger.debug("Transcribed audio of %d bytes", len(data))
        return _segments(response.json())
