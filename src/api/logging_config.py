"""
Logging configuration module.
This module must be imported before any other modules to ensure proper logging setup.
"""

import logging
import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Configure logging before any other imports
AZURE_BASIC_LOGGING_LEVEL = os.getenv("AZURE_BASIC_LOGGING_LEVEL", "INFO").upper()
AZURE_PACKAGE_LOGGING_LEVEL = os.getenv("AZURE_PACKAGE_LOGGING_LEVEL", "WARNING").upper()
AZURE_LOGGING_PACKAGES = [
    pkg.strip() for pkg in os.getenv("AZURE_LOGGING_PACKAGES", "").split(",") if pkg.strip()
]

# Configure logging (this will be the first logging configuration)
logging.basicConfig(
    level=getattr(logging, AZURE_BASIC_LOGGING_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Configure Azure package loggers
for logger_name in AZURE_LOGGING_PACKAGES:
    logging.getLogger(logger_name).setLevel(getattr(logging, AZURE_PACKAGE_LOGGING_LEVEL, logging.WARNING))

# Log that configuration is complete
logger = logging.getLogger(__name__)
logger.info(f"Logging configured - Basic: {AZURE_BASIC_LOGGING_LEVEL}, Azure packages: {AZURE_PACKAGE_LOGGING_LEVEL}, Packages: {AZURE_LOGGING_PACKAGES}")
