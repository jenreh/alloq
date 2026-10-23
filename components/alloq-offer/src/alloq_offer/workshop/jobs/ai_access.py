"""The AI for a job; a missing setup fails the job with a message users read."""

from alloq_offer.workshop.ai.agents import DemoOfferAi, PydanticOfferAi, create_offer_ai
from alloq_offer.workshop.ai.port import AiUnavailableError
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.jobs.registry import PermanentJobError


def job_ai(config: WorkshopConfig) -> PydanticOfferAi | DemoOfferAi:
    try:
        return create_offer_ai(config)
    except AiUnavailableError as exc:
        raise PermanentJobError(str(exc)) from exc
