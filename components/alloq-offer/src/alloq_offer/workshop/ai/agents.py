"""``OfferAi`` on pydantic-ai agents."""

import logging
from functools import cache
from importlib import resources

import httpx
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.azure import AzureProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from alloq_offer.workshop.ai.port import (
    AiTransientError,
    AiUnavailableError,
    ChapterRequest,
    MapRequest,
    ReviewRequest,
    SourceText,
)
from alloq_offer.workshop.ai.render import (
    render_chapter,
    render_map_request,
    render_review,
    render_sources,
)
from alloq_offer.workshop.ai.schemas import (
    ProposedBriefing,
    ProposedChapter,
    ProposedMap,
    ProposedReview,
)
from alloq_offer.workshop.configuration import WorkshopConfig

logger = logging.getLogger(__name__)

MAP_PROMPT = "map_v1"
BRIEFING_PROMPT = "briefing_v1"
MAP_ADDITIONS_PROMPT = "map_additions_v1"
CHAPTER_PROMPT = "chapter_v1"
REVIEW_PROMPT = "review_v1"
NOT_CONFIGURED = "Die KI ist nicht eingerichtet."
RATE_LIMITED = 429
SERVER_ERROR = 500


@cache
def load_prompt(name: str) -> str:
    return (
        resources.files("alloq_offer.workshop.ai.prompts")
        .joinpath(f"{name}.md")
        .read_text(encoding="utf-8")
    )


def build_azure_model(config: WorkshopConfig) -> Model:
    azure = config.azure_openai
    if not (azure.endpoint and azure.chat_deployment):
        raise AiUnavailableError(NOT_CONFIGURED)
    provider = AzureProvider(
        azure_endpoint=azure.endpoint,
        api_version=azure.api_version,
        api_key=azure.api_key.get_secret_value(),
    )
    return OpenAIChatModel(azure.chat_deployment, provider=provider)


class PydanticOfferAi:
    """Proposals from a pydantic-ai model; outputs are validated or retried."""

    map_prompt_version = MAP_PROMPT
    briefing_prompt_version = BRIEFING_PROMPT
    chapter_prompt_version = CHAPTER_PROMPT
    review_prompt_version = REVIEW_PROMPT
    map_additions_prompt_version = MAP_ADDITIONS_PROMPT

    def __init__(self, model: Model, config: WorkshopConfig, name: str) -> None:
        self._model = model
        self._config = config
        self.model_name = name

    async def _run[T](
        self, output: type[T], prompt: str, user_prompt: str, label: str
    ) -> T:
        agent = Agent(
            self._model,
            name=label,
            output_type=output,
            instructions=load_prompt(prompt),
            retries=2,
            model_settings=ModelSettings(timeout=self._config.ai_timeout_seconds),
        )
        try:
            result = await agent.run(
                user_prompt,
                usage_limits=UsageLimits(request_limit=self._config.ai_request_limit),
            )
        except ModelHTTPError as exc:
            if exc.status_code == RATE_LIMITED or exc.status_code >= SERVER_ERROR:
                raise AiTransientError(label) from exc
            raise AiUnavailableError(label) from exc
        except (httpx.TransportError, TimeoutError) as exc:
            raise AiTransientError(label) from exc
        except UnexpectedModelBehavior as exc:
            raise AiUnavailableError(label) from exc
        usage = result.usage
        logger.info(
            "Model run %s: %d requests, %d input and %d output tokens",
            label,
            usage.requests,
            usage.input_tokens,
            usage.output_tokens,
        )
        return result.output

    async def propose_map(self, sources: list[SourceText]) -> ProposedMap:
        data = render_sources(sources, self._config.ai_max_input_chars)
        return await self._run(ProposedMap, MAP_PROMPT, data, "propose_map")

    async def propose_briefing(self, sources: list[SourceText]) -> ProposedBriefing:
        data = render_sources(sources, self._config.ai_max_input_chars)
        return await self._run(
            ProposedBriefing, BRIEFING_PROMPT, data, "propose_briefing"
        )

    async def propose_chapter(self, request: ChapterRequest) -> ProposedChapter:
        data = render_chapter(request, self._config.ai_max_input_chars)
        return await self._run(ProposedChapter, CHAPTER_PROMPT, data, "propose_chapter")

    async def propose_map_additions(self, request: MapRequest) -> ProposedMap:
        data = render_map_request(request, self._config.ai_max_input_chars)
        return await self._run(
            ProposedMap, MAP_ADDITIONS_PROMPT, data, "propose_map_additions"
        )

    async def propose_review(self, request: ReviewRequest) -> ProposedReview:
        data = render_review(request, self._config.ai_max_input_chars)
        return await self._run(ProposedReview, REVIEW_PROMPT, data, "propose_review")


def create_offer_ai(config: WorkshopConfig) -> PydanticOfferAi:
    return PydanticOfferAi(
        build_azure_model(config), config, config.azure_openai.chat_deployment
    )
