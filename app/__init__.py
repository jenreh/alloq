import logging

import appkit_commons  # noqa: F401  (loads .env with override, PROFILES included)
from dotenv import load_dotenv

from app.desktop.profile import activate_desktop_profile, prepare_embedded_backend

activate_desktop_profile()
prepare_embedded_backend()

from app.configuration import configure  # noqa: E402

logger = logging.getLogger(__name__)
logger.info("Configuring application...")

load_dotenv()
configuration = configure()
