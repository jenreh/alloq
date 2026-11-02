"""The AI for a job; a missing setup fails the job with a message users read."""

from alloq_offer.workshop.ai.agents import DemoOfferAi, PydanticOfferAi, create_offer_ai
from alloq_offer.workshop.ai.port import AiSetupError, AiUnavailableError
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.jobs.registry import PermanentJobError


def job_ai(config: WorkshopConfig) -> PydanticOfferAi | DemoOfferAi:
    try:
        return create_offer_ai(config)
    except AiUnavailableError as exc:
        raise PermanentJobError(str(exc)) from exc


def failure_message(exc: AiUnavailableError, default: str) -> str:
    """What the job tells users: the setup problem, else its own message."""
    return str(exc) if isinstance(exc, AiSetupError) else default
