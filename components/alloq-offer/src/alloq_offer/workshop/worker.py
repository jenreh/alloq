"""Background worker of the offer workshop, started with the app."""

import logging

from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.jobs import (  # noqa: F401  (registers the handlers)
    extract_source,
    initial_draft,
)
from alloq_offer.workshop.jobs.registry import registered_kinds
from alloq_offer.workshop.jobs.runner import JobRunner
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)


async def offer_workshop_worker() -> None:
    """Lifespan task: run queued workshop jobs while the app is up."""
    config = service_registry().get(WorkshopConfig)
    if not config.worker_enabled:
        logger.info("Offer workshop worker is disabled")
        return
    logger.info("Offer workshop worker started, handlers: %s", registered_kinds())
    await JobRunner(config).run_forever()
