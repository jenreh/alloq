"""``OfferAi`` on pydantic-ai agents."""

import logging
from collections.abc import Awaitable, Callable

import httpx
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.azure import AzureProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from alloq_offer.workshop.ai.demo import DemoOfferAi
from alloq_offer.workshop.ai.port import (
    AiSetupError,
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
    ProposedTable,
)
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.services.prompts import (
    BRIEFING_PROMPT,
    CHAPTER_PROMPT,
    MAP_ADDITIONS_PROMPT,
    MAP_PROMPT,
    REVIEW_PROMPT,
    Prompt,
    PromptMissingError,
    load_prompt,
)

logger = logging.getLogger(__name__)

NOT_CONFIGURED = (
    "Die KI ist nicht eingerichtet. Bitte hinterlegen Sie den Azure-OpenAI-Zugang "
    "in der Konfiguration."
)
RATE_LIMITED = 429
SERVER_ERROR = 500

PromptLoader = Callable[[str], Awaitable[Prompt]]


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
    """Proposals from a pydantic-ai model; outputs are validated or retried.

    The system prompts are the active versions in the database, read once per
    instance (one job); each ``*_prompt_version`` names the version that ran
    (``chapter@3``), or is empty when no call ran.
    """

    def __init__(
        self,
        model: Model,
        config: WorkshopConfig,
        name: str,
        prompts: PromptLoader = load_prompt,
    ) -> None:
        self._model = model
        self._config = config
        self._prompts = prompts
        self._loaded: dict[str, Prompt] = {}
        self.model_name = name

    def _label(self, name: str) -> str:
        prompt = self._loaded.get(name)
        return prompt.label if prompt else ""

    async def _prompt(self, name: str) -> Prompt:
        if name not in self._loaded:
            try:
                self._loaded[name] = await self._prompts(name)
            except PromptMissingError as exc:
                raise AiSetupError(str(exc)) from exc
        return self._loaded[name]

    @property
    def map_prompt_version(self) -> str:
        return self._label(MAP_PROMPT)

    @property
    def briefing_prompt_version(self) -> str:
        return self._label(BRIEFING_PROMPT)

    @property
    def chapter_prompt_version(self) -> str:
        return self._label(CHAPTER_PROMPT)

    @property
    def review_prompt_version(self) -> str:
        return self._label(REVIEW_PROMPT)

    @property
    def map_additions_prompt_version(self) -> str:
        return self._label(MAP_ADDITIONS_PROMPT)

    async def _run[T](
        self, output: type[T], prompt_name: str, user_prompt: str, label: str
    ) -> T:
        prompt = await self._prompt(prompt_name)
        agent = Agent(
            self._model,
            name=label,
            output_type=output,
            instructions=prompt.instructions,
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

    async def propose_table(self, request: ChapterRequest) -> ProposedTable:
        data = render_chapter(request, self._config.ai_max_input_chars)
        return await self._run(ProposedTable, CHAPTER_PROMPT, data, "propose_table")

    async def propose_map_additions(self, request: MapRequest) -> ProposedMap:
        data = render_map_request(request, self._config.ai_max_input_chars)
        return await self._run(
            ProposedMap, MAP_ADDITIONS_PROMPT, data, "propose_map_additions"
        )

    async def propose_review(self, request: ReviewRequest) -> ProposedReview:
        data = render_review(request, self._config.ai_max_input_chars)
        return await self._run(ProposedReview, REVIEW_PROMPT, data, "propose_review")


def create_offer_ai(config: WorkshopConfig) -> PydanticOfferAi | DemoOfferAi:
    """The configured model; ``demo`` quotes the sources instead of a model."""
    if config.ai_provider == "demo":
        return DemoOfferAi()
    return PydanticOfferAi(
        build_azure_model(config), config, config.azure_openai.chat_deployment
    )
