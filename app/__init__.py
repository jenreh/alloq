import logging

import appkit_commons  # noqa: F401  (loads .env with override, PROFILES included)
from dotenv import load_dotenv

from app.configuration import configure

logger = logging.getLogger(__name__)
logger.info("Configuring application...")

load_dotenv()
configuration = configure()
